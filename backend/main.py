import os
import requests
import warnings
warnings.filterwarnings('ignore')

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from assistant.assistant import Assistant
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env.development')  # Load environment variables from a .env file

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.post("/message")
async def receive_message(request: Request):
    form_data = await request.form()
    # Extract the key fields
    from_number = form_data.get("From")
    to_number = form_data.get("To")

    if not from_number or not to_number:
        raise HTTPException(status_code=400, detail="Missing From or To fields in webhook payload")

    body: str | None = None
    assistant = Assistant()

    # Detect audio media attachment and attempt transcription
    media_content_type = form_data.get("MediaContentType0")
    if media_content_type and media_content_type.startswith("audio/"):
        media_url = form_data.get("MediaUrl0")
        if not media_url:
            raise HTTPException(status_code=400, detail="MediaUrl0 is missing for audio message")

        # Twilio media URLs require basic auth with Account SID & Auth Token
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            raise HTTPException(status_code=500, detail="Twilio credentials not configured for audio retrieval")

        try:
            resp = requests.get(media_url, auth=(account_sid, auth_token), timeout=30)
            resp.raise_for_status()
            audio_bytes = resp.content
            # Derive a filename extension from content-type if possible
            ext = "ogg" if media_content_type == "audio/ogg" else media_content_type.split("/")[-1][:5]
            transcript = await assistant.transcribe_audio(audio_bytes, filename=f"voice.{ext}")
            print(f"Transcription result: {transcript}")
            body = transcript.strip() or "(Unintelligible audio or empty transcription)"
        except Exception as e:
            print(f"[receive_message] Audio transcription failed: {e}")
            body = "(Error transcribing audio message)"
    else:
        body = form_data.get("Body") or ""

    try:
        message = await assistant.generate_response(prompt=body, from_number=from_number, to_number=to_number)
        print(f"Generated message: {message}")
    except Exception as e:
        print(f"[receive_message] Error generating response: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate response")

    return {"status": "Message sent"}