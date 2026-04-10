# Agent Flow Studio

Local-first visual builder for LLM workflows and agent flows.

## What Is In Git

- Application code under `server.py`, `engine/`, and `static/`
- Docs such as `ROADMAP.md`
- Example config templates such as `.env.example` and `settings.example.json`
- Curated example flows under `examples/flows/`

## What Stays Local

This app generates and edits local runtime data while you use it. Those files are intentionally ignored:

- `assistant/` runtime memory, persona, chat, and logs
- `flows/` saved local flows
- `prompts/` local prompt library entries
- `subflows/` local reusable flow fragments
- `output/` generated outputs
- `vector_stores/` local embedding stores
- `settings.json` local settings

The server recreates missing local files and folders as needed.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` if you want environment-based configuration.
4. Optionally create `settings.json` from `settings.example.json` for local defaults.

## Run

```bash
python server.py
```

Then open `http://localhost:8090`.

## Examples

The editor includes an `Examples` button that loads tracked demo flows from `examples/flows/` onto the canvas as new unsaved local flows.

## Configuration

Configuration priority is:

1. Environment variables
2. `settings.json`

Supported keys are shown in `.env.example` and `settings.example.json`.
