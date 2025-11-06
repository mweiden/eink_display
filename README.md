# eink_display
[![CI](https://github.com/mweiden/eink_display/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

Python application for driving a Waveshare 7.5" e-ink display with a daily calendar view rendered from Google Calendar data. See [DESIGN.md](DESIGN.md) for the architectural plan.

## Development

- Review the contributor guidelines in [AGENTS.md](AGENTS.md) before making changes.
- Create and activate a virtual environment (e.g., `python -m venv .venv && source .venv/bin/activate`).
- Install development dependencies as needed (e.g., `pip install -r requirements-dev.txt` if using a shared requirements file).
- Configure the renderer preview directory (see below) to iterate on layouts without e-ink hardware attached.

### Rendering preview images

We now call the original React renderer directly via a small Fastify/Puppeteer service that ships with the repository
(`eink_display/rendering/node_renderer`). The Python helpers automatically install dependencies on first use, but you can also do
so manually:

```bash
cd eink_display/rendering/node_renderer
PUPPETEER_SKIP_DOWNLOAD=1 npm install
```

Render previews from Python by spinning up the service and posting events to it:

```python
from datetime import datetime

from eink_display.rendering import CalendarEvent, NodeRenderClient, NodeRenderServer

event = CalendarEvent(
    title="Design Review",
    start=datetime(2024, 5, 1, 9, 0),
    end=datetime(2024, 5, 1, 9, 45),
    location="Room 2A",
)

with NodeRenderServer() as server:
    client = NodeRenderClient(server.base_url)
    client.render([event], output_path="calendar.png")
```

The server emits a `480×800` layout rendered at `2×` device scale (`960×1600` PNG) so text remains crisp on the Waveshare panel.
This is the same PNG that the integration tests validate.

## Testing

Run the full automated test suite locally before opening a pull request:

```bash
pytest
```

The continuous integration workflow mirrors this command to help ensure consistent results.
