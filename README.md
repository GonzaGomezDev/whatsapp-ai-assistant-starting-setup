# WhatsApp AI Assistant

An intelligent WhatsApp chatbot powered by OpenAI's GPT-4o-mini, LangGraph, and Twilio. This assistant can understand voice messages, manage calendar events, search the web, and maintain conversation context across sessions.

## Features

### Voice Message Support
- Automatic transcription of WhatsApp voice messages using OpenAI Whisper
- Seamless conversion of audio to text for natural voice interactions

### Google Calendar Integration
- **Create Events**: Schedule meetings with attendees, locations, and descriptions
- **View Events**: Query upcoming events within specific time ranges
- **Delete Events**: Remove calendar events by start time
- Automatic email invitations to attendees via Google Calendar

### Web Search
- Real-time web search capabilities powered by Tavily
- Up-to-date information retrieval for answering current events and factual queries

### Persistent Memory
- PostgreSQL-backed conversation history using LangGraph checkpointing
- Context retention across multiple conversation sessions
- Each phone number maintains its own conversation thread

### Intelligent Routing
- Automatic tool selection based on user intent
- Multi-turn conversations with tool chaining
- Streaming responses for real-time feedback

## Architecture

- **Framework**: FastAPI for REST API endpoints
- **AI Model**: OpenAI GPT-4o-mini with function calling
- **Agent Framework**: LangGraph for stateful conversational workflows
- **Database**: PostgreSQL for conversation checkpointing
- **Messaging**: Twilio WhatsApp API
- **Voice Processing**: OpenAI Whisper for transcription

## Prerequisites

- Python 3.10+
- PostgreSQL database
- Twilio account with WhatsApp sandbox or approved business number
- OpenAI API key
- Google Cloud project with Calendar API enabled
- Tavily API key for web search

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/GonzaGomezDev/whatsapp-ai-assistant-starting-setup.git
cd whatsapp-ai-assistant-demo
```

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env.development` file in the `backend` directory:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token

# Database Configuration
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=langgraph

# Tavily Search API
TAVILY_API_KEY=your_tavily_api_key

# Google Calendar (Optional - uses defaults if not set)
GOOGLE_CALENDAR_SCOPES=https://www.googleapis.com/auth/calendar.events
GOOGLE_CALENDAR_CREDENTIALS_FILE=./credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=./token.json
GOOGLE_CALENDAR_DEFAULT_CALENDAR_ID=primary
```

### 4. Setup PostgreSQL Database

```bash
# Create database
psql -U postgres
CREATE DATABASE langgraph;
\q
```

The application will automatically create the required tables on first run.

### 5. Setup Google Calendar OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Desktop application)
5. Download the credentials JSON file
6. Save it as `credentials.json` in the `backend` directory
7. On first run, the application will open a browser for OAuth consent
8. The token will be saved in `token.json` for subsequent uses

### 6. Configure Twilio WhatsApp Webhook

1. Log in to your [Twilio Console](https://console.twilio.com/)
2. Navigate to Messaging → Try it out → Send a WhatsApp message
3. Set the webhook URL to: `https://your-domain.com/message`
4. For local development, use ngrok:
   ```bash
   ngrok http 8000
   ```
   Then use the ngrok URL: `https://your-ngrok-url.ngrok.io/message`

### 7. Run the Application

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

## Usage

### Text Messages
Send any text message to your WhatsApp bot number. The assistant will:
- Understand your intent
- Use appropriate tools (calendar, search, etc.)
- Respond with relevant information

### Voice Messages
Send a voice message, and the assistant will:
- Transcribe your audio using Whisper
- Process the transcribed text
- Respond as if you sent a text message

### Example Conversations

**Creating a Calendar Event:**
```
User: "Schedule a meeting tomorrow at 2 PM with john@example.com about project review"
Assistant: "I've created the meeting for tomorrow at 2:00 PM. John has been invited and will receive an email notification."
```

**Web Search:**
```
User: "What's the latest news about artificial intelligence?"
Assistant: [Searches web and provides current information]
```

**Voice Interaction:**
```
User: [Sends voice message saying "What's on my calendar this week?"]
Assistant: "Here are your upcoming events this week: [lists events]"
```

## Project Structure

```
whatsapp-ai-assistant-demo/
├── backend/
│   ├── assistant/
│   │   ├── assistant.py      # Main Assistant class with LangGraph setup
│   │   ├── state.py           # State management for conversations
│   │   └── tool_calls.py      # Tool execution and routing logic
│   ├── tools/
│   │   ├── __init__.py
│   │   └── calendar.py        # Google Calendar integration
│   ├── prompts/
│   │   └── _evo_001           # System prompt for the assistant
│   ├── main.py                # FastAPI application and endpoints
│   ├── models.py              # SQLAlchemy database models
│   ├── requirements.txt       # Python dependencies
│   ├── credentials.json       # Google OAuth credentials (not in repo)
│   └── token.json             # Google OAuth token (not in repo)
└── README.md
```

## Key Components

### Assistant Class (`assistant/assistant.py`)
- Initializes LangGraph state machine
- Manages conversation flow with conditional routing
- Handles tool execution and message streaming
- Maintains PostgreSQL checkpointing for conversation persistence

### Tools (`tools/calendar.py`)
- Google Calendar event creation, retrieval, and deletion
- OAuth 2.0 authentication with token caching
- Timezone-aware datetime handling

### Main API (`main.py`)
- `/message` endpoint for Twilio webhook
- Handles both text and voice messages
- Database integration for message logging

## Contributing

### Adding New Tools

1. Create a new tool function in `tools/` directory:
```python
def my_new_tool(param1: str, param2: int) -> dict:
    """
    Tool description for the AI.
    
    Args:
        param1: Description of parameter
        param2: Description of parameter
    
    Returns: Result dictionary
    """
    # Your tool logic here
    return {"result": "success"}
```

2. Import and add to the tools list in `assistant/assistant.py`:
```python
from tools import my_new_tool

self.tools = [
    TavilySearch(max_results=5),
    create_calendar_event,
    my_new_tool,  # Add your new tool
]
```

### Customizing the System Prompt

Edit `backend/prompts/_evo_001` to modify the assistant's personality, behavior, and instructions.

### Database Models

Add new models in `models.py` for additional data persistence needs.

## Troubleshooting

### Tool Execution Errors
- Check that all environment variables are set correctly
- Verify API keys are valid and have proper permissions
- Review logs for detailed error messages

### Google Calendar OAuth Issues
- Delete `token.json` and re-authenticate
- Ensure Calendar API is enabled in Google Cloud Console
- Verify `credentials.json` is in the correct location

### Database Connection Issues
- Confirm PostgreSQL is running
- Check database credentials in environment variables
- Ensure database `langgraph` exists

### Twilio Webhook Failures
- Verify webhook URL is publicly accessible
- Check Twilio console for webhook logs
- Ensure server is running and reachable

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with [LangChain](https://github.com/langchain-ai/langchain) and [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [OpenAI](https://openai.com/) GPT-4o-mini
- Messaging via [Twilio](https://www.twilio.com/)
- Web search by [Tavily](https://tavily.com/)
