# E-Ink Calendar Display Design

## Design "Fat-marker" Sketch

<img width="862" height="829" alt="Screenshot 2025-11-02 at 2 02 00 PM" src="https://github.com/user-attachments/assets/0b4425b3-d8ca-4170-aded-a21cfca94eca" />

## System Overview
- **Platform**: Raspberry Pi 5 running Raspberry Pi OS.
- **Display**: Waveshare 7.5" e-Paper (800×480) mounted vertically.
- **Core Responsibilities**:
  1. Fetch today's Google Calendar events.
  2. Render the day view following the provided visual design.
  3. Refresh the display at 30-second intervals (:00 and :30).
  4. Handle hardware lifecycle (init, refresh, sleep) safely.

## Architecture
```
+------------------------+
| CLI / Main Application |
+-----------+------------+
            |
            v
+-----------+------------+      +-----------------+
| Scheduler & Refresh Loop +----> Logging/Telemetry|
+-----------+------------+      +-----------------+
            |
            v
+------------------------+
| Calendar Service Layer |
+-----------+------------+
            |
            v
+------------------------+      +------------------------+
| Rendering Pipeline     +----->| Display Driver Adapter |
+------------------------+      +------------------------+
            |
            v
      Waveshare Display
```

### Modules
1. **Configuration & Secrets** (`eink_display/config.py`)
   - Load environment-based settings (calendar IDs, timezone, refresh cadence).
   - Read Google API credentials from file path or env var.
   - Validate on startup and surface actionable error messages.

2. **Calendar Client** (`eink_display/calendar/google_client.py`)
   - Wrap Google Calendar API for authenticated requests.
   - Fetch all events in the local day window (midnight to midnight, local TZ).
   - Normalize events into internal dataclass (title, start/end, location, is_all_day, attendees?).
   - Provide caching and retry logic with exponential backoff.

3. **Scheduling & Refresh** (`eink_display/scheduler.py`)
   - Calculate next trigger aligned to second :00 or :30.
   - Sleep until target and execute refresh callback.
   - Detect drift; if the cycle takes too long, immediately re-align.
   - Expose manual override flag for immediate rendering (e.g., `--once`).

4. **Rendering Pipeline** (`eink_display/rendering/`)
   - Layout constants describing columns/rows, fonts, padding.
   - Utility to translate events into drawable blocks (current time indicator, meeting cards, header, footer metadata).
   - Use Pillow to draw text and shapes, applying monochrome conversion (Floyd–Steinberg dithering if needed).
   - Provide preview output to PNG for local debugging without device.
   - Include localization helpers for time strings (12h vs 24h if needed).

5. **Display Driver Adapter** (`eink_display/display/waveshare.py`)
   - Encapsulate Waveshare `epd7in5_V2` driver lifecycle (init, clear, display buffer, sleep).
   - Accept Pillow image buffer and convert to the driver format.
   - Offer mock driver for development (saves PNGs/logs instead of pushing to hardware).

6. **Application Orchestration** (`eink_display/app.py`)
   - Parse CLI arguments, initialize logging.
   - Load configuration, initialize calendar client, renderer, display adapter.
   - Start scheduler; on each tick fetch events, render image, update display.
   - Handle exceptions with retries and fallback rendering (e.g., "Data unavailable" panel).
   - On shutdown ensure display sleeps and resources released.

7. **Testing & Tooling**
   - Unit tests for calendar normalization, layout calculations, scheduler timing logic.
   - Integration test pipeline mocking Google API and display driver to validate end-to-end refresh.
   - Linting (e.g., `ruff` or `flake8`) and formatting via `black` for consistent style.
   - Include `make` or `tox` tasks to run tests and lint.

## Data Flow
1. Scheduler wakes at :00/:30.
2. Calendar client retrieves and normalizes today's events.
3. Renderer produces 800×480 portrait bitmap.
4. Display adapter sends bitmap to hardware (or mock driver in dev).
5. Logging system records success/failure with timestamps.

## Error Handling & Resilience
- Retry Google API calls with exponential backoff; cache last successful response.
- On repeated failures, display last known good calendar alongside warning banner.
- Monitor for network timeouts and record metrics (logs or optional Prometheus exporter).
- Protect against hardware initialization failure by retrying and optionally rebooting display.

## Configuration Matrix
| Setting | Description | Default |
| --- | --- | --- |
| `GOOGLE_CREDENTIALS_PATH` | Path to service account JSON or OAuth token. | Required |
| `CALENDAR_IDS` | Comma-separated Google Calendar IDs to aggregate. | Primary calendar |
| `TIMEZONE` | IANA timezone string. | System default |
| `REFRESH_INTERVAL_SECONDS` | Refresh cadence (should remain 30). | `30` |
| `DISPLAY_ORIENTATION` | `portrait` or `landscape`. | `portrait` |
| `PREVIEW_OUTPUT_PATH` | Directory for optional PNG previews. | Disabled |

## Outstanding Questions
- Authentication flow (service account vs OAuth) for unattended Pi deployment.
- Handling overlapping events visually within constrained width.
- Strategy for font management (bundled fonts vs system fonts).
- Should we include weather or other metadata when calendar is empty?

## Next Steps
1. Implement configuration loader and document environment setup.
2. Establish Google Calendar client with mocked tests.
3. Scaffold rendering module with placeholder layout to validate fonts/sizing.
4. Integrate display driver and ensure mock driver works for CI.
5. Build main loop and verify scheduler timing accuracy.
6. Set up CI pipeline for linting and tests on commits.
