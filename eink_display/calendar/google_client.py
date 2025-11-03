"""Google Calendar client for retrieving events for the E-Ink display."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as time_, timedelta
from typing import Callable, List, Mapping, MutableMapping, Optional, Sequence

from google.auth.credentials import Credentials
from google.auth.exceptions import TransportError
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalendarEvent:
    """Normalized representation of a Google Calendar event."""

    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None


class CalendarApiError(RuntimeError):
    """Raised when the Google Calendar API repeatedly fails."""


class GoogleCalendarClient:
    """Client wrapper around the Google Calendar API."""

    def __init__(
        self,
        credentials: Optional[Credentials],
        calendar_ids: Sequence[str],
        timezone: str | ZoneInfo,
        *,
        service: Optional[Resource] = None,
        max_retries: int = 3,
        retry_initial_delay: float = 1.0,
        retry_backoff: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Initialize the client.

        Args:
            credentials: Google API credentials used to authenticate requests. Ignored when
                ``service`` is provided.
            calendar_ids: Google Calendar identifiers to fetch events from.
            timezone: IANA timezone name or ``ZoneInfo`` instance defining the local timezone.
            service: Pre-built Google API service (primarily for testing).
            max_retries: Maximum number of retries for API calls.
            retry_initial_delay: Base delay before the first retry (seconds).
            retry_backoff: Multiplier applied to the delay after each retry.
            sleep: Sleep function used between retries (primarily for testing).
        """
        if not calendar_ids:
            raise ValueError("At least one calendar ID must be provided.")

        self.calendar_ids: List[str] = list(calendar_ids)
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(str(timezone))
        self.max_retries = max_retries
        self.retry_initial_delay = retry_initial_delay
        self.retry_backoff = retry_backoff
        self._sleep = sleep

        if service is not None:
            self._service = service
        else:
            if credentials is None:
                raise ValueError("Credentials must be provided when service is not injected.")
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def fetch_todays_events(
        self,
        *,
        now: Optional[datetime] = None,
        calendar_ids: Optional[Sequence[str]] = None,
    ) -> List[CalendarEvent]:
        """Return normalized events for the current day in the configured timezone."""
        active_calendar_ids = list(calendar_ids) if calendar_ids else self.calendar_ids
        reference_time = self._ensure_timezone(now) if now is not None else datetime.now(tz=self.timezone)
        start_of_day = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events: List[CalendarEvent] = []
        for calendar_id in active_calendar_ids:
            events.extend(self._fetch_events_for_calendar(calendar_id, start_of_day, end_of_day))

        events.sort(key=lambda event: (event.start, event.end, event.title))
        return events

    # ------------------------------------------------------------------
    def _fetch_events_for_calendar(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
    ) -> List[CalendarEvent]:
        def execute_request() -> Mapping[str, object]:
            request = (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    timeZone=self._timezone_name,
                )
            )
            return request.execute()

        response = self._execute_with_backoff(execute_request)
        items = response.get("items", []) if isinstance(response, MutableMapping) else []
        normalized: List[CalendarEvent] = []
        for item in items:
            try:
                normalized.append(self._normalize_event(item))
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to normalize event from calendar %s: %s", calendar_id, exc)
        return normalized

    def _normalize_event(self, event: Mapping[str, object]) -> CalendarEvent:
        title = str(event.get("summary") or "Untitled Event")
        start_info = self._extract_time_info(event.get("start"))
        end_info = self._extract_time_info(event.get("end"))
        location = event.get("location")

        return CalendarEvent(
            title=title,
            start=start_info,
            end=end_info,
            location=str(location) if location is not None else None,
        )

    def _extract_time_info(self, value: object) -> datetime:
        if not isinstance(value, Mapping):
            raise CalendarApiError("Event time data is missing or malformed.")

        if "dateTime" in value:
            dt = self._parse_datetime(str(value["dateTime"]))
        elif "date" in value:
            dt_date = date.fromisoformat(str(value["date"]))
            dt = datetime.combine(dt_date, time_.min, tzinfo=self.timezone)
        else:
            raise CalendarApiError("Event time data lacks 'dateTime' or 'date'.")

        return self._ensure_timezone(dt)

    def _parse_datetime(self, value: str) -> datetime:
        cleaned = value.rstrip("Z") + ("+00:00" if value.endswith("Z") else "")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError as exc:  # pragma: no cover - depends on malformed API response
            raise CalendarApiError(f"Unable to parse datetime value: {value}") from exc
        return parsed

    def _ensure_timezone(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.timezone)
        return dt.astimezone(self.timezone)

    @property
    def _timezone_name(self) -> str:
        return getattr(self.timezone, "key", str(self.timezone))

    def _execute_with_backoff(self, func: Callable[[], Mapping[str, object]]) -> Mapping[str, object]:
        attempt = 0
        delay = self.retry_initial_delay
        while True:
            try:
                return func()
            except (HttpError, TransportError, TimeoutError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise CalendarApiError("Google Calendar API request failed after retries.") from exc
                logger.warning(
                    "Google Calendar API request failed (attempt %d/%d): %s", attempt, self.max_retries, exc
                )
                self._sleep(delay)
                delay *= self.retry_backoff


__all__ = ["CalendarEvent", "GoogleCalendarClient", "CalendarApiError"]
