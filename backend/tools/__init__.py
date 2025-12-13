"""
Tools module for the WhatsApp AI Assistant.
Exports LangChain-compatible tools for calendar and reminder management.
"""

from langchain_core.tools import tool
from typing import List, Optional, Literal
from .calendar import create_calendar_event as _create_calendar_event
from .calendar import get_calendar_events as _get_calendar_events  
from .calendar import delete_calendar_event as _delete_calendar_event

@tool
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
        start: ISO 8601 datetime string. If timezone is missing, UTC is assumed.
        end: ISO 8601 datetime string. Must be after start.
        description: Optional event description/body.
        attendees: Optional list of attendee emails.
        location: Optional location string.
        calendar_id: Calendar to insert into. Defaults to env or 'primary'.

    Returns: The created event resource from Google Calendar API.
    """
    return _create_calendar_event(summary, start, end, description, attendees, location, calendar_id)


@tool
def get_calendar_events(
    time_min: str, 
    time_max: str, 
    calendar_id: Optional[str] = None
) -> List[dict]:
    """
    Retrieve events from Google Calendar within a specified time range.

    Args:
        time_min: ISO 8601 datetime string representing the start of the time range (inclusive).
        time_max: ISO 8601 datetime string representing the end of the time range (exclusive).
        calendar_id: Calendar to query. Defaults to env or 'primary'.

    Returns: A list of event resources from Google Calendar API.
    """
    return _get_calendar_events(time_min, time_max, calendar_id)


@tool
def delete_calendar_event(
    start_time: str, 
    calendar_id: Optional[str] = None
) -> str:
    """
    Delete an event from Google Calendar by its start time.

    Args:
        start_time: The start time of the event to delete.
        calendar_id: Calendar from which to delete the event. Defaults to env or 'primary'.
	
    Returns: Success message.
    """
    _delete_calendar_event(start_time, calendar_id)
    return "Event deleted successfully"

# Export the tools for easy importing
__all__ = [
    "create_calendar_event",
    "get_calendar_events", 
    "delete_calendar_event",
    "create_reminder",
    "update_reminder_status"
]