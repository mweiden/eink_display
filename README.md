# eink_display
[![CI](https://github.com/mweiden/eink_display/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

Python application for driving a Waveshare 7.5" e-ink display with a daily calendar view rendered from Google Calendar data. See [DESIGN.md](DESIGN.md) for the architectural plan.

## Configuration

The application reads configuration from environment variables or an optional `.env` file in the working directory. At minimum, set the following values before starting the program:

| Variable | Description |
| --- | --- |
| `GOOGLE_CREDENTIALS_PATH` | Absolute path to the Google service account JSON used for Calendar API access. The file must exist when the application starts. |
| `CALENDAR_IDS` | Comma-separated list of Google Calendar IDs to display (e.g., `primary,team@example.com`). |

Example `.env` file:

```dotenv
GOOGLE_CREDENTIALS_PATH=/home/pi/secrets/service-account.json
CALENDAR_IDS=primary,team@example.com
```

## Development

- Review the contributor guidelines in [AGENTS.md](AGENTS.md) before making changes.
- Create and activate a virtual environment (e.g., `python -m venv .venv && source .venv/bin/activate`).
- Install development dependencies as needed (e.g., `pip install -r requirements-dev.txt` if using a shared requirements file).
- Configure the renderer preview directory (see below) to iterate on layouts without e-ink hardware attached.

### Rendering preview images

The rendering layer supports a preview mode that writes PNG files for local debugging. Instantiate the renderer with a preview
directory and call `render_day` with a name for the image:

```python
from datetime import datetime

from eink_display.rendering import CalendarEvent, DayRenderer, RendererConfig

config = RendererConfig(preview_output_dir="previews")
renderer = DayRenderer(config)
image = renderer.render_day(
    events=[
        CalendarEvent(
            title="Design Review",
            start=datetime(2024, 5, 1, 9, 0),
            end=datetime(2024, 5, 1, 10, 0),
            location="Room 2A",
        )
    ],
    now=datetime.now(),
    preview_name="sample",
)
```

The renderer saves `previews/sample.png` and returns the Pillow `Image` instance for additional inspection or unit testing.

## Testing

Run the full automated test suite locally before opening a pull request:

```bash
pytest
```

The continuous integration workflow mirrors this command to help ensure consistent results.
