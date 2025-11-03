"""Calendar integrations for the E-Ink display application."""

from .google_client import CalendarEvent, GoogleCalendarClient, CalendarApiError

__all__ = [
    "CalendarEvent",
    "GoogleCalendarClient",
    "CalendarApiError",
]
