"""
Google Calendar utility functions intended to be exposed as tools for the AI assistant.

Features:
- Local OAuth2 user credentials (Installed App) using token persistence
- Create calendar events with attendees, location, and reminders

Environment variables (optional, with sensible defaults):
- GOOGLE_CALENDAR_SCOPES: Comma-separated scopes. Default: https://www.googleapis.com/auth/calendar.events
- GOOGLE_CALENDAR_CREDENTIALS_FILE: Path to OAuth client secrets JSON. Default: ./credentials.json
- GOOGLE_CALENDAR_TOKEN_FILE: Path to persist the OAuth token. Default: ./token.json
- GOOGLE_CALENDAR_DEFAULT_CALENDAR_ID: Default calendar id to use. Default: primary

Usage (programmatic):
	from tools.calendar import create_calendar_event
	create_calendar_event(
		summary="Team sync",
		start="2025-09-18T15:00:00Z",
		end="2025-09-18T15:30:00Z",
		description="Weekly check-in",
		attendees=["alice@example.com", "bob@example.com"],
		location="Google Meet"
	)

Note: The first run will require an interactive OAuth consent in a browser. The token will be cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence

import os

from dotenv import load_dotenv

# Google API imports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Load env once for local execution/dev. In prod, process env is already set.
load_dotenv(dotenv_path='.env.development')


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
	v = os.getenv(name)
	if v is None or v == "":
		return default
	return v


SCOPES = [s.strip() for s in (_env("GOOGLE_CALENDAR_SCOPES", "https://www.googleapis.com/auth/calendar.events") or "").split(",") if s.strip()]
CREDENTIALS_FILE = _env("GOOGLE_CALENDAR_CREDENTIALS_FILE", "./credentials.json")
TOKEN_FILE = _env("GOOGLE_CALENDAR_TOKEN_FILE", "./token.json")
DEFAULT_CALENDAR_ID = _env("GOOGLE_CALENDAR_DEFAULT_CALENDAR_ID", "primary")


@dataclass
class CalendarEvent:
	summary: str
	start: datetime
	end: datetime
	description: Optional[str] = None
	attendees: Optional[Sequence[str]] = None
	location: Optional[str] = None
	calendar_id: str = DEFAULT_CALENDAR_ID


def _load_credentials() -> Credentials:
	"""
	Load stored credentials or run the OAuth Installed App flow.
	Returns a google.oauth2.credentials.Credentials object.
	"""
	creds: Optional[Credentials] = None

	# Load existing token if present
	if TOKEN_FILE and os.path.exists(TOKEN_FILE):
		try:
			creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
		except Exception:
			creds = None

	# Refresh if expired
	if creds and creds.expired and creds.refresh_token:
		try:
			creds.refresh(Request())
		except Exception as e:
			# Token refresh failed; fall back to new auth flow
			creds = None

	# If no valid creds available, start browser-based flow
	if not creds:
		if not CREDENTIALS_FILE or not os.path.exists(CREDENTIALS_FILE):
			raise RuntimeError(
				"Google Calendar credentials not configured. Set GOOGLE_CALENDAR_CREDENTIALS_FILE to your OAuth client secrets JSON."
			)
		flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
		try:
			# Use local server flow if possible for smoother UX
			creds = flow.run_local_server(port=0)
		except Exception:
			# Fallback to console (no browser) if local server flow fails
			creds = flow.run_console()

		# Save the credentials for next run
		if TOKEN_FILE:
			try:
				with open(TOKEN_FILE, "w", encoding="utf-8") as token:
					token.write(creds.to_json())
			except Exception:
				# Non-fatal; proceed without persisting
				pass

	return creds


def _ensure_rfc3339(dt_str: str) -> datetime:
	"""
	Parse ISO 8601 date string to datetime with tzinfo.
	Accepts 'Z' for UTC. If no tz is provided, assume UTC.
	"""
	try:
		# Normalize trailing Z
		norm = dt_str.replace("Z", "+00:00")
		dt = datetime.fromisoformat(norm)
	except Exception as e:
		raise ValueError(f"Invalid datetime format (expect ISO 8601): {e}")

	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return dt


def _to_event_body(ev: CalendarEvent) -> dict:
	def to_dt_payload(dt: datetime) -> dict:
		# Provide RFC3339 timestamp; omit timeZone to avoid mismatches when tzname is not an IANA zone
		return {"dateTime": dt.isoformat()}

	attendees_payload = (
		[{"email": a} for a in (ev.attendees or []) if isinstance(a, str) and a.strip()]
		or None
	)

	body: dict = {
		"summary": ev.summary,
		"start": to_dt_payload(ev.start),
		"end": to_dt_payload(ev.end),
	}
	if ev.description:
		body["description"] = ev.description
	if attendees_payload:
		body["attendees"] = attendees_payload
	if ev.location:
		body["location"] = ev.location

	# Provide default reminders: 10 minutes popup (can be edited later)
	body["reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}

	return body


def create_calendar_event(
	summary: str,
	start: str,
	end: str,
	description: Optional[str] = None,
	attendees: Optional[List[str]] = None,
	location: Optional[str] = None,
	calendar_id: Optional[str] = None,
) -> dict:
	"""
	Create a Google Calendar event.

	Args:
		summary: Event title.
		start: ISO 8601 datetime string. If timezone is missing, UTC -3 is assumed.
		end: ISO 8601 datetime string. Must be after start.
		description: Optional event description/body.
		attendees: Optional list of attendee emails.
		location: Optional location string.
		calendar_id: Calendar to insert into. Defaults to env or 'primary'.

	Returns: The created event resource (dict) from Google Calendar API.
	"""
	if not summary or not isinstance(summary, str):
		raise ValueError("summary must be a non-empty string")

	start_dt = _ensure_rfc3339(start)
	end_dt = _ensure_rfc3339(end)
	if end_dt <= start_dt:
		raise ValueError("end must be after start")

	ev = CalendarEvent(
		summary=summary,
		start=start_dt,
		end=end_dt,
		description=description,
		attendees=attendees,
		location=location,
		calendar_id=(calendar_id or DEFAULT_CALENDAR_ID),
	)

	creds = _load_credentials()
	try:
		service = build("calendar", "v3", credentials=creds, cache_discovery=False)
		body = _to_event_body(ev)
		created = service.events().insert(
			calendarId=ev.calendar_id,
			body=body,
			sendUpdates="all",
		).execute()
		return created
	except HttpError as e:
		# Provide more context
		raise RuntimeError(f"Google Calendar API error: {e}") from e

def get_calendar_events(time_min: str, time_max: str, calendar_id: Optional[str] = None) -> List[dict]:
    """
    Retrieve events from Google Calendar within a specified time range.

    Args:
        time_min: ISO 8601 datetime string representing the start of the time range (inclusive).
        time_max: ISO 8601 datetime string representing the end of the time range (exclusive).
        calendar_id: Calendar to query. Defaults to env or 'primary'.

    Returns: A list of event resources (dict) from Google Calendar API.
    """
    creds = _load_credentials()
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        events = service.events().list(
            calendarId=calendar_id or DEFAULT_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events.get("items", [])
    except HttpError as e:
        # Provide more context
        raise RuntimeError(f"Google Calendar API error: {e}") from e

def delete_calendar_event(start_time: str, calendar_id: Optional[str] = None) -> None:
    """
    Delete an event from Google Calendar.

    Args:
        start_time: The start time of the event to delete.
        calendar_id: Calendar from which to delete the event. Defaults to env or 'primary'.
	
    Returns: None
    """
    creds = _load_credentials()
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        events = service.events().list(
            calendarId=calendar_id or DEFAULT_CALENDAR_ID,
            timeMin=start_time,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        items = events.get("items", [])
        if not items:
            raise ValueError("No event found with the specified start time.")
        event_id = items[0]['id']
        service.events().delete(
            calendarId=calendar_id or DEFAULT_CALENDAR_ID,
            eventId=event_id
        ).execute()
    except HttpError as e:
        # Provide more context
        raise RuntimeError(f"Google Calendar API error: {e}") from e

__all__ = [
	"CalendarEvent",
	"create_calendar_event",
	"get_calendar_events",
	"delete_calendar_event",
]

