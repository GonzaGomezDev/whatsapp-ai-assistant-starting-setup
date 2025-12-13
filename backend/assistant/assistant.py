import os
import io 

from contextlib import ExitStack
from datetime import date
from models import SessionLocal, Message

from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END
from twilio.rest import Client
from openai import AsyncOpenAI

from assistant.state import State
from assistant.tool_calls import BasicToolNode
from tools import (
    create_calendar_event,
    get_calendar_events,
    delete_calendar_event
)

if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("TWILIO_ACCOUNT_SID") or not os.environ.get("TWILIO_AUTH_TOKEN"):
    raise EnvironmentError("OPENAI_API_KEY, TWILIO_ACCOUNT_SID, and TWILIO_AUTH_TOKEN must be set in environment variables.")

# Build a psycopg-compatible connection string
_db_user = os.getenv('DB_USER', 'postgres')
_db_pass = os.getenv('DB_PASSWORD', 'password')
_db_host = os.getenv('DB_HOST', 'localhost')
_db_port = os.getenv('DB_PORT', '5432')
_db_name = os.getenv('DB_NAME', 'langgraph')

# Preferred URL form (no +psycopg2)
connection_string = f"postgresql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"

# Also prepare a DSN fallback (space separated) if URL fails
dsn_fallback = f"host={_db_host} port={_db_port} dbname={_db_name} user={_db_user} password={_db_pass}"

class Assistant:
    """LangChain agent wrapper with Postgres-backed checkpointing.

    IMPORTANT: PostgresSaver.from_conn_string returns a *context manager* that must be
    entered to obtain the actual saver instance. Passing the raw context manager causes
    errors like: '_GeneratorContextManager' object has no attribute 'get_next_version'.
    """

    def __init__(self):
        self.tools = [
            TavilySearch(max_results=5),
            create_calendar_event,
            get_calendar_events,
            delete_calendar_event,
        ]
        self.agent = init_chat_model("gpt-4o-mini", temperature=0.5, use_responses_api=True).bind_tools(self.tools)
        self.graph_builder = StateGraph(State)
        self.tool_node = BasicToolNode(tools=self.tools)
        self.graph_builder.add_node("tools", self.tool_node)

        self.graph_builder.add_conditional_edges(
            "chat",
            BasicToolNode.route_tools,
            # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
            # It defaults to the identity function, but if you
            # want to use a node named something else apart from "tools",
            # You can update the value of the dictionary to something else
            # e.g., "tools": "my_tools"
            {"tools": "tools", END: END},
        )
        self.graph_builder.add_edge("tools", "chat")
        
        self._exit_stack = ExitStack()
        self.memory: PostgresSaver | None = None
        last_err: Exception | None = None

        # Try URL form first, then DSN.
        for candidate in (connection_string, dsn_fallback):
            try:
                cm = PostgresSaver.from_conn_string(candidate)
                self.memory = self._exit_stack.enter_context(cm)
                break
            except Exception as e:
                last_err = e
                print(f"[LangChain] Failed to init PostgresSaver with '{candidate}': {e}")
        if self.memory is None:
            raise RuntimeError(
                "Could not initialize PostgresSaver with either URL or DSN. "
                "Check DB credentials and network accessibility." 
                + (f" Last error: {last_err}" if last_err else "")
            )

        self.memory.setup()

        self.twilio_client = Client()

        # Load assistant instructions once during initialization
        with open("./prompts/_evo_001", "r", encoding="utf-8") as fp:
            self.assistant_instructions = fp.read()

        self.graph_builder.add_node("chat", self.chat)
        self.graph_builder.add_edge(START, "chat")
        self.graph_builder.add_edge("chat", END)
        self.graph = self.graph_builder.compile(checkpointer=self.memory)

    def chat(self, state: State):
        """Chat node that processes messages and generates responses."""
        return {
            "messages": [self.agent.invoke(state["messages"])]
        }
    
    def close(self):
        """Gracefully close the PostgresSaver context."""
        try:
            if hasattr(self, "_exit_stack") and self._exit_stack:
                self._exit_stack.close()
        except Exception as e:
            print(f"[LangChain] Error while closing checkpointer: {e}")

    def __del__(self):  # best-effort cleanup
        self.close()

    def _load_conversation_history(self, from_number: str, to_number: str, limit: int = 20):
        """Load recent conversation history from database"""
        db = SessionLocal()
        try:
            # Get messages between these two numbers (both directions)
            messages = db.query(Message).filter(
                ((Message._from == from_number) & (Message._to == to_number)) |
                ((Message._from == to_number) & (Message._to == from_number))
            ).order_by(Message.id.desc()).limit(limit).all()
            
            # Reverse to get chronological order
            messages.reverse()
            
            # Convert to LangChain message format
            formatted_messages = []
            for msg in messages:
                role = "user" if msg.message_type == "user" else "assistant"
                formatted_messages.append({
                    "role": role,
                    "content": msg.content
                })
            
            return formatted_messages
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            return []
        finally:
            db.close()

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        """Transcribe audio bytes using Whisper.

        Args:
            audio_bytes: Raw audio file bytes (ogg/mp3/wav/webm etc.)
            filename: A representative filename with extension so the API can infer format.

        Returns:
            The transcribed text (may be empty string if transcription fails silently).
        """
        # Wrap bytes in a file-like object with a name attr (required by OpenAI lib)
        audio_file_obj = io.BytesIO(audio_bytes)
        audio_file_obj.name = filename  # type: ignore[attr-defined]

        try:
            model = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            transcription = await model.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_obj,
                response_format="text",
            )
            return transcription or ""
        except Exception as e:
            # Log and gracefully degrade; upstream can decide fallback behavior
            print(f"[transcribe_audio] Failed to transcribe audio: {e}")
            return ""

    async def generate_response(self, prompt: str, from_number: str, to_number: str) -> str:
        # Store prompt in DB
        db = SessionLocal()
        try:
            msg_record = Message(
                _from=from_number,
                _to=to_number,
                content=prompt,
                created_at=date.today().isoformat(),
                message_type="user"
            )
            db.add(msg_record)
            db.commit()
        except Exception as e:
            print(f"Error saving incoming message to DB: {e}")
        finally:
            db.close()
        
        # Create messages with system instructions, and current prompt
        messages = [
            {"role": "system", "content": self.assistant_instructions + f"\n\nCurrent date is {date.today().isoformat()} and default timezone is UTC -3 (ART)."}
        ]
        
        # Add current user message
        messages.append({"role": "user", "content": prompt})
        
        # Use phone number as thread ID for persistent memory
        config = {"configurable": {"thread_id": from_number}}

        final_response = ""
        
        print(f"[Assistant] Generating response for prompt: {prompt}")
        for step in self.graph.stream({"messages": messages}, config, stream_mode="messages"):
            # step is a tuple (message, metadata) when using stream_mode="messages"
            if isinstance(step, tuple) and len(step) == 2:
                message_chunk, metadata = step
                
                # Only process AI messages that have content
                if (hasattr(message_chunk, 'content') and 
                    message_chunk.content):
                    
                    # Handle both string and list content (Responses API can return lists)
                    content = message_chunk.content
                    if isinstance(content, list):
                        # Extract text from list of content blocks
                        text_content = ""
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                text_content += item['text']
                            elif isinstance(item, str):
                                text_content += item
                            elif hasattr(item, 'text'):
                                text_content += item.text
                        content = text_content
                    
                    # Filter out JSON responses and empty content
                    if content and not str(content).startswith('{'):
                        final_response += content
                    
        # Send the complete response via Twilio
        if final_response:
            self.twilio_client.messages.create(
                body=final_response,
                from_=to_number,
                to=from_number
            )

            # Store AI response in DB
            db = SessionLocal()
            try:
                msg_record = Message(
                    _from=to_number,
                    _to=from_number,
                    content=final_response,
                    created_at=date.today().isoformat(),
                    message_type="ai"
                )
                db.add(msg_record)
                db.commit()
            except Exception as e:
                print(f"Error saving AI response to DB: {e}")
            finally:
                db.close()
            
        return final_response