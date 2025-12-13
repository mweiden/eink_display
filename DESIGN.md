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
| Rendering Service |
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
   - Read Google API credentials from file path or env var for the Node renderer.
   - Validate on startup and surface actionable error messages.

2. **Scheduling & Refresh** (`eink_display/scheduler.py`)
   - Calculate next trigger aligned to second :00 or :30.
   - Sleep until target and execute refresh callback.
   - Detect drift; if the cycle takes too long, immediately re-align.
   - Expose manual override flag for immediate rendering (e.g., `--once`).

3. **Rendering Pipeline** (`eink_display/rendering/`)
   - A bundled Fastify/Puppeteer service owns both the Google Calendar fetch and the React rendering.
   - The service queries Google Calendar directly using configured credentials, renders the JSX to HTML, and screenshots the root
     route at 2× device scale using headless Chromium.
   - `NodeRenderServer` manages the service lifecycle; `NodeRenderClient` only pulls the already-rendered PNG from the root path (no
     Python event payloads).
   - Dependencies are vendored in `rendering/node_renderer` (React component, server harness, Google API client, and Chromium
     binary via `@sparticuz/chromium`).
   - Integration tests spawn the service to guarantee parity with the reference layout without requiring Google access (the server
     falls back to sample events in that case).

4. **Display Driver Adapter** (`eink_display/display/waveshare.py`)
   - Encapsulate Waveshare `epd7in5_V2` driver lifecycle (init, clear, display buffer, sleep).
   - Accept Pillow image buffer and convert to the driver format.
   - Offer mock driver for development (saves PNGs/logs instead of pushing to hardware).

5. **Application Orchestration** (`eink_display/app.py`)
   - Parse CLI arguments, initialize logging.
   - Initialize renderer and display adapter; the renderer no longer receives event payloads from Python.
   - Start scheduler; on each tick fetch the pre-rendered PNG from the Node server root and update the display.
   - Handle exceptions with retries and fallback rendering (e.g., "Data unavailable" panel).
   - On shutdown ensure display sleeps and resources released.

7. **Testing & Tooling**
   - Unit tests for renderer interaction, scheduler timing logic, and display plumbing.
   - Integration test pipeline spinning up the Node renderer while mocking the display driver.
   - Linting (e.g., `ruff` or `flake8`) and formatting via `black` for consistent style.
   - Include `make` or `tox` tasks to run tests and lint.

## Data Flow
1. Scheduler wakes at :00/:30.
2. Node renderer fetches and normalizes today's Google Calendar events.
3. Node renderer produces the 800×480 portrait PNG at the root route.
4. Python downloads the PNG from `http://localhost:<port>/`, converts it to the e-ink bitmap, and sends it to hardware (or mock
   driver in dev).
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
2. Harden Node renderer error handling and logging around Google Calendar access.
3. Integrate display driver and ensure mock driver works for CI.
4. Build main loop and verify scheduler timing accuracy.
5. Set up CI pipeline for linting and tests on commits.
