from __future__ import annotations

from datetime import datetime
from unittest import mock

import pytest
from googleapiclient.errors import HttpError
from zoneinfo import ZoneInfo

from eink_display.calendar.google_client import (
    CalendarApiError,
    CalendarEvent,
    GoogleCalendarClient,
)


def _make_http_error(status: int = 500, reason: str = "Server Error") -> HttpError:
    response = mock.Mock()
    response.status = status
    response.reason = reason
    return HttpError(resp=response, content=b"error")


def test_fetch_todays_events_normalizes_fields() -> None:
    timezone = ZoneInfo("America/Los_Angeles")
    service = mock.Mock()
    events_resource = service.events.return_value
    list_request = events_resource.list.return_value
    list_request.execute.return_value = {
        "items": [
            {
                "summary": "Morning Meeting",
                "location": "Conference Room",
                "start": {"dateTime": "2024-01-15T09:00:00-08:00"},
                "end": {"dateTime": "2024-01-15T10:00:00-08:00"},
            },
            {
                "summary": "All Day Conference",
                "start": {"date": "2024-01-15"},
                "end": {"date": "2024-01-16"},
            },
        ]
    }

    client = GoogleCalendarClient(
        credentials=None,
        calendar_ids=["primary"],
        timezone=timezone,
        service=service,
    )

    reference = datetime(2024, 1, 15, 12, 30, tzinfo=timezone)
    events = client.fetch_todays_events(now=reference)

    assert events == [
        CalendarEvent(
            title="All Day Conference",
            start=datetime(2024, 1, 15, 0, 0, tzinfo=timezone),
            end=datetime(2024, 1, 16, 0, 0, tzinfo=timezone),
            location=None,
        ),
        CalendarEvent(
            title="Morning Meeting",
            start=datetime(2024, 1, 15, 9, 0, tzinfo=timezone),
            end=datetime(2024, 1, 15, 10, 0, tzinfo=timezone),
            location="Conference Room",
        ),
    ]

    list_kwargs = events_resource.list.call_args.kwargs
    assert list_kwargs["timeMin"] == "2024-01-15T00:00:00-08:00"
    assert list_kwargs["timeMax"] == "2024-01-16T00:00:00-08:00"
    assert list_kwargs["timeZone"] == "America/Los_Angeles"
    assert list_kwargs["calendarId"] == "primary"
    assert list_kwargs["singleEvents"] is True
    assert list_kwargs["orderBy"] == "startTime"


def test_fetch_todays_events_retries_on_failure() -> None:
    timezone = ZoneInfo("UTC")
    service = mock.Mock()
    events_resource = service.events.return_value
    list_request = events_resource.list.return_value
    list_request.execute.side_effect = [
        _make_http_error(),
        {"items": []},
    ]

    sleep_mock = mock.Mock()
    client = GoogleCalendarClient(
        credentials=None,
        calendar_ids=["primary"],
        timezone=timezone,
        service=service,
        sleep=sleep_mock,
        retry_initial_delay=0.1,
    )

    result = client.fetch_todays_events(now=datetime(2024, 1, 15, 8, tzinfo=timezone))
    assert result == []
    assert sleep_mock.call_args_list == [mock.call(0.1)]
    assert list_request.execute.call_count == 2


def test_fetch_todays_events_raises_after_exhausting_retries() -> None:
    timezone = ZoneInfo("UTC")
    service = mock.Mock()
    events_resource = service.events.return_value
    list_request = events_resource.list.return_value
    list_request.execute.side_effect = [_make_http_error()] * 3

    sleep_mock = mock.Mock()
    client = GoogleCalendarClient(
        credentials=None,
        calendar_ids=["primary"],
        timezone=timezone,
        service=service,
        sleep=sleep_mock,
        max_retries=2,
        retry_initial_delay=0.05,
    )

    with pytest.raises(CalendarApiError):
        client.fetch_todays_events(now=datetime(2024, 1, 15, 8, tzinfo=timezone))

    assert sleep_mock.call_args_list == [mock.call(0.05), mock.call(0.05 * 2)]
    assert list_request.execute.call_count == 3
