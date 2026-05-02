# Status: Project Ready

## Structure & Status
Project restructured and tactical MFD console implemented.

## Architecture
- **Contract-First**: Pydantic schemas in `src/server/schema.py`.
- **Backend**: Flask-based simulation server in `src/server/main.py`.
- **Frontend**: Tactical MFD interface in `src/web/` (Vanilla HTML/CSS/JS).
- **Environment**: Managed via `uv`.

## Features
- **Tactical Map**: Dynamic satellite tracking (ISS, Hubble, MetOp) and simulated wildfire ignition zones.
- **Telemetry**: Real-time hardware health (CPU, RAM, Temp) and container status.
- **Mission Control**: Operational queue and fire simulator triggers.
- **Aesthetics**: CRT scanlines, phosphor green glows, and monospaced typography.

## Operations
- **Start**: `bash scripts/launch_dashboard.command`
- **Stop**: `bash scripts/stop_dashboard.command`
- **Test**: `uv run pytest tests/test_server.py`

---
**[Module] [Task] [Complete]**
`uv run pytest tests/test_server.py` && **Green**.
