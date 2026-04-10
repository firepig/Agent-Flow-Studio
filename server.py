from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from engine.executor import FlowExecutor
from engine.exporter import export_flow
from engine.llm_providers import LLMError, create_provider
from engine.memory_consolidation import consolidate_short_term_to_long_term

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

FLOWS_DIR = Path("flows")
EXAMPLES_DIR = _BASE_DIR / "examples" / "flows"
SETTINGS_FILE = _BASE_DIR / "settings.json"

pending_executions: dict[str, dict] = {}


async def _memory_consolidation_background(settings: dict) -> None:
    try:
        await consolidate_short_term_to_long_term(settings)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    FLOWS_DIR.mkdir(exist_ok=True)
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("{}", encoding="utf-8")
    yield


app = FastAPI(title="Agent Flow Studio", lifespan=lifespan)


# ------------------------------------------------------------------
# Static / Index
# ------------------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse("static/index.html")


# ------------------------------------------------------------------
# Flows CRUD
# ------------------------------------------------------------------

@app.get("/api/flows")
async def list_flows():
    flows = []
    for fp in sorted(FLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            node_count = len(
                data.get("flow_data", {})
                .get("drawflow", {})
                .get("Home", {})
                .get("data", {})
            )
            flows.append({
                "id": data.get("id", fp.stem),
                "name": data.get("name", "Untitled"),
                "description": data.get("description", ""),
                "node_count": node_count,
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return flows


@app.get("/api/examples")
async def list_examples():
    examples = []
    if not EXAMPLES_DIR.exists():
        return examples

    for fp in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            graph = data.get("flow_graph", {})
            examples.append({
                "id": data.get("id", fp.stem),
                "name": data.get("name", fp.stem),
                "description": data.get("description", ""),
                "complexity": data.get("complexity", "simple"),
                "modules": data.get("modules", []),
                "use_case": data.get("use_case", ""),
                "node_count": len(graph.get("nodes", [])),
            })
        except (json.JSONDecodeError, OSError, AttributeError):
            continue

    return examples


@app.get("/api/examples/{example_id}")
async def get_example(example_id: str):
    fp = EXAMPLES_DIR / f"{example_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Example not found")
    return json.loads(fp.read_text(encoding="utf-8"))


@app.get("/api/flows/{flow_id}")
async def get_flow(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")
    return json.loads(fp.read_text(encoding="utf-8"))


@app.post("/api/flows")
async def create_flow(body: dict):
    flow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    flow = {
        "id": flow_id,
        "name": body.get("name", "Untitled"),
        "description": body.get("description", ""),
        "flow_data": body.get("flow_data", {}),
        "created_at": now,
        "updated_at": now,
    }
    (FLOWS_DIR / f"{flow_id}.json").write_text(
        json.dumps(flow, indent=2), encoding="utf-8",
    )
    return flow


@app.put("/api/flows/{flow_id}")
async def update_flow(flow_id: str, body: dict):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")
    existing = json.loads(fp.read_text(encoding="utf-8"))
    existing["name"] = body.get("name", existing["name"])
    existing["description"] = body.get("description", existing["description"])
    existing["flow_data"] = body.get("flow_data", existing["flow_data"])
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    fp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


@app.delete("/api/flows/{flow_id}")
async def delete_flow(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")
    fp.unlink()
    return {"ok": True}


# ------------------------------------------------------------------
# Flow Execution
# ------------------------------------------------------------------

@app.post("/api/flows/{flow_id}/execute")
async def start_execution(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")

    flow = json.loads(fp.read_text(encoding="utf-8"))
    settings = _load_settings()
    execution_id = str(uuid.uuid4())

    pending_executions[execution_id] = {
        "flow_data": flow["flow_data"],
        "settings": settings,
    }
    return {"execution_id": execution_id}


@app.websocket("/ws/execute/{execution_id}")
async def ws_execute(websocket: WebSocket, execution_id: str):
    await websocket.accept()

    entry = pending_executions.pop(execution_id, None)
    if entry is None:
        await websocket.send_text(json.dumps({
            "type": "flow_error",
            "error": f"Unknown execution_id: {execution_id}",
        }))
        await websocket.close()
        return

    executor = FlowExecutor(entry["flow_data"], entry["settings"])
    ws_open = True

    async def send_event(event: dict) -> None:
        nonlocal ws_open
        if not ws_open:
            return
        try:
            await websocket.send_text(json.dumps(event))
        except (WebSocketDisconnect, RuntimeError):
            ws_open = False

    async def run_flow() -> None:
        try:
            await executor.execute(progress_callback=send_event)
        except Exception as exc:
            await send_event({"type": "flow_error", "error": str(exc)})

    async def listen_client() -> None:
        nonlocal ws_open
        try:
            while ws_open:
                msg_text = await websocket.receive_text()
                msg = json.loads(msg_text)
                if msg.get("type") == "hitl_response":
                    await executor.submit_hitl_response(
                        msg.get("node_id", ""),
                        msg.get("action", "reject"),
                        msg.get("data", ""),
                    )
        except (WebSocketDisconnect, RuntimeError):
            ws_open = False
            executor.cancel()

    flow_task = asyncio.create_task(run_flow())
    listen_task = asyncio.create_task(listen_client())

    await flow_task
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass

    if ws_open:
        try:
            await websocket.close()
        except Exception:
            pass


# ------------------------------------------------------------------
# Test Single Node
# ------------------------------------------------------------------

@app.post("/api/test-node")
async def test_node(body: dict):
    node_type = body.get("node_type", "")
    node_data = body.get("node_data", {})
    input_text = body.get("input_text", "")
    settings = _load_settings()

    executor = FlowExecutor({"drawflow": {"Home": {"data": {}}}}, settings)
    chunks: list[str] = []

    async def capture(event: dict) -> None:
        if event.get("type") == "node_output":
            chunks.append(event.get("chunk", ""))

    try:
        output = await executor._run_node("test", node_type, node_data, input_text, [input_text], capture)
        return {"ok": True, "output": output, "stream": "".join(chunks)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ------------------------------------------------------------------
# Debug Execution (step-through)
# ------------------------------------------------------------------

@app.post("/api/flows/{flow_id}/debug")
async def start_debug(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")

    flow = json.loads(fp.read_text(encoding="utf-8"))
    settings = _load_settings()
    execution_id = str(uuid.uuid4())

    pending_executions[execution_id] = {
        "flow_data": flow["flow_data"],
        "settings": settings,
        "debug": True,
    }
    return {"execution_id": execution_id}


@app.websocket("/ws/debug/{execution_id}")
async def ws_debug(websocket: WebSocket, execution_id: str):
    await websocket.accept()

    entry = pending_executions.pop(execution_id, None)
    if entry is None:
        await websocket.send_text(json.dumps({
            "type": "flow_error",
            "error": f"Unknown execution_id: {execution_id}",
        }))
        await websocket.close()
        return

    executor = FlowExecutor(entry["flow_data"], entry["settings"])
    ws_open = True
    debug_signal: asyncio.Queue[dict] = asyncio.Queue()

    async def send_event(event: dict) -> None:
        nonlocal ws_open
        if not ws_open:
            return
        try:
            await websocket.send_text(json.dumps(event))
        except (WebSocketDisconnect, RuntimeError):
            ws_open = False

    async def run_debug() -> None:
        try:
            await executor.execute_debug(
                progress_callback=send_event,
                debug_signal=debug_signal,
            )
        except Exception as exc:
            await send_event({"type": "flow_error", "error": str(exc)})

    async def listen_client() -> None:
        nonlocal ws_open
        try:
            while ws_open:
                msg_text = await websocket.receive_text()
                msg = json.loads(msg_text)
                msg_type = msg.get("type", "")
                if msg_type in ("debug_step", "debug_continue", "debug_stop", "debug_edit"):
                    await debug_signal.put(msg)
                elif msg_type == "hitl_response":
                    await executor.submit_hitl_response(
                        msg.get("node_id", ""),
                        msg.get("action", "reject"),
                        msg.get("data", ""),
                    )
        except (WebSocketDisconnect, RuntimeError):
            ws_open = False
            executor.cancel()
            await debug_signal.put({"type": "debug_stop"})

    flow_task = asyncio.create_task(run_debug())
    listen_task = asyncio.create_task(listen_client())

    await flow_task
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass

    if ws_open:
        try:
            await websocket.close()
        except Exception:
            pass


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------

@app.get("/api/flows/{flow_id}/export")
async def export_flow_endpoint(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")

    flow = json.loads(fp.read_text(encoding="utf-8"))
    flow_name = flow.get("name", "workflow")
    settings = _load_settings()

    zip_bytes = export_flow(flow["flow_data"], flow_name, settings)
    safe_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in flow_name
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    merged = _load_settings()
    return {
        "openai_api_key": _mask_key(merged.get("openai_api_key", "")),
        "anthropic_api_key": _mask_key(merged.get("anthropic_api_key", "")),
        "ollama_base_url": merged.get("ollama_base_url", "http://localhost:11434"),
        "default_provider": merged.get("default_provider", "openai"),
        "default_model": merged.get("default_model", "gpt-4o"),
        "openai_api_key_from_env": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "anthropic_api_key_from_env": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
    }


@app.post("/api/settings")
async def save_settings(body: dict):
    """Persist only settings.json contents. Never write environment-sourced API keys into the file."""
    stored = _load_settings_file_raw()

    for key in ("ollama_base_url", "default_provider", "default_model"):
        if key in body:
            stored[key] = body[key]

    for key in ("openai_api_key", "anthropic_api_key"):
        val = body.get(key)
        if not isinstance(val, str):
            continue
        if val.startswith("*"):
            continue
        if val.strip():
            stored[key] = val.strip()
        else:
            stored.pop(key, None)

    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(stored, indent=2), encoding="utf-8")
    return {"ok": True}


# ------------------------------------------------------------------
# NL Flow Builder (Phase 2.3)
# ------------------------------------------------------------------

@app.post("/api/generate-flow")
async def generate_flow(body: dict):
    description = body.get("description", "")
    if not description.strip():
        raise HTTPException(400, "Description is required")

    settings = _load_settings()
    provider_type = settings.get("default_provider", "openai")
    model = settings.get("default_model")
    api_key = None
    if provider_type == "openai":
        api_key = settings.get("openai_api_key", "")
    elif provider_type == "anthropic":
        api_key = settings.get("anthropic_api_key", "")

    provider = create_provider(
        provider_type,
        api_key=api_key or None,
        model=model,
        base_url=settings.get("ollama_base_url"),
    )

    system_prompt = """You are a flow graph generator for Agent Flow Studio. Given a description, produce a JSON flow graph.

Available node types and their data fields:
- start: {input_text}
- llm: {provider, model, system_prompt, user_prompt_template, temperature, max_tokens}
- prompt_template: {template} — use {{input}} for incoming data
- conditional: {condition_type (contains|not_contains|equals|regex), condition_value}
- code: {code, unrestricted} — use input_data for input, set output
- merge: {merge_mode (concatenate|json_array), separator}
- output: {output_name}
- shell: {command_template, shell_type (powershell|bash|python), timeout}
- http_request: {method, url_template, headers_json, body_template, extract_path}
- file_read: {file_path_template}
- file_write: {file_path, write_mode (write|append)}
- loop: {loop_mode (code|llm|shell), max_iterations, condition_type, condition_value, loop_code}
- react_agent: {goal, provider, model, max_iterations, allowed_tools, system_prompt}
- conversation_memory: {memory_id, strategy (full|sliding_window), max_messages, role, output_format}

Output a JSON object with this structure:
{
  "nodes": [
    {"id": "1", "type": "start", "x": 100, "y": 200, "data": {"label": "Start", "input_text": "..."}, "inputs": 0, "outputs": 1},
    {"id": "2", "type": "llm", "x": 400, "y": 200, "data": {"label": "Generate", ...}, "inputs": 1, "outputs": 1},
    ...
  ],
  "connections": [
    {"from_node": "1", "from_output": "output_1", "to_node": "2", "to_input": "input_1"},
    ...
  ]
}

Position nodes left-to-right with ~300px horizontal spacing. Always start with a 'start' node and end with an 'output' node.
Return ONLY valid JSON, no markdown fences or explanation."""

    try:
        result = await provider.generate(
            system_prompt=system_prompt,
            user_prompt=f"Create a flow for: {description}",
            temperature=0.5,
            max_tokens=4000,
        )
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:])
            if result.endswith("```"):
                result = result[:-3]
        flow_graph = json.loads(result)
        return {"ok": True, "flow_graph": flow_graph}
    except json.JSONDecodeError:
        return {"ok": False, "error": "LLM returned invalid JSON. Try again with a simpler description.", "raw": result[:1000]}
    except LLMError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected error: {exc}"}


# ------------------------------------------------------------------
# Prompt Library (Phase 3.3)
# ------------------------------------------------------------------

PROMPTS_DIR = Path("prompts")


@app.get("/api/prompts")
async def list_prompts():
    PROMPTS_DIR.mkdir(exist_ok=True)
    prompts = []
    for fp in sorted(PROMPTS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            prompts.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return prompts


@app.post("/api/prompts")
async def create_prompt(body: dict):
    PROMPTS_DIR.mkdir(exist_ok=True)
    prompt_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    prompt = {
        "id": prompt_id,
        "name": body.get("name", "Untitled Prompt"),
        "description": body.get("description", ""),
        "tags": body.get("tags", []),
        "template": body.get("template", ""),
        "created_at": now,
        "updated_at": now,
    }
    (PROMPTS_DIR / f"{prompt_id}.json").write_text(
        json.dumps(prompt, indent=2), encoding="utf-8",
    )
    return prompt


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    fp = PROMPTS_DIR / f"{prompt_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Prompt not found")
    fp.unlink()
    return {"ok": True}


# ------------------------------------------------------------------
# Sub-Flows (Phase 3.1)
# ------------------------------------------------------------------

SUBFLOWS_DIR = Path("subflows")


@app.get("/api/subflows")
async def list_subflows():
    SUBFLOWS_DIR.mkdir(exist_ok=True)
    subflows = []
    for fp in sorted(SUBFLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            subflows.append({
                "id": data.get("id", fp.stem),
                "name": data.get("name", "Untitled"),
                "description": data.get("description", ""),
                "input_ports": data.get("input_ports", 1),
                "output_ports": data.get("output_ports", 1),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return subflows


@app.post("/api/subflows")
async def create_subflow(body: dict):
    SUBFLOWS_DIR.mkdir(exist_ok=True)
    subflow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    subflow = {
        "id": subflow_id,
        "name": body.get("name", "Sub-Flow"),
        "description": body.get("description", ""),
        "input_ports": body.get("input_ports", 1),
        "output_ports": body.get("output_ports", 1),
        "flow_data": body.get("flow_data", {}),
        "created_at": now,
        "updated_at": now,
    }
    (SUBFLOWS_DIR / f"{subflow_id}.json").write_text(
        json.dumps(subflow, indent=2), encoding="utf-8",
    )
    return subflow


@app.get("/api/subflows/{subflow_id}")
async def get_subflow(subflow_id: str):
    fp = SUBFLOWS_DIR / f"{subflow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Sub-flow not found")
    return json.loads(fp.read_text(encoding="utf-8"))


@app.delete("/api/subflows/{subflow_id}")
async def delete_subflow(subflow_id: str):
    fp = SUBFLOWS_DIR / f"{subflow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Sub-flow not found")
    fp.unlink()
    return {"ok": True}


# ------------------------------------------------------------------
# Vector Stores (Phase 4)
# ------------------------------------------------------------------

VECTOR_STORES_DIR = Path("vector_stores")


@app.get("/api/vector-stores")
async def list_vector_stores():
    VECTOR_STORES_DIR.mkdir(exist_ok=True)
    stores = []
    for fp in sorted(VECTOR_STORES_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            stores.append({
                "name": fp.stem,
                "count": len(data) if isinstance(data, list) else 0,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return stores


@app.delete("/api/vector-stores/{name}")
async def delete_vector_store(name: str):
    fp = VECTOR_STORES_DIR / f"{name}.json"
    if fp.exists():
        fp.unlink()
    return {"ok": True}


# ------------------------------------------------------------------
# App Interface (standalone UI for flows)
# ------------------------------------------------------------------

@app.get("/app/{flow_id}")
async def serve_app(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")
    return FileResponse(Path("static/app.html"))


@app.get("/api/app/{flow_id}/config")
async def app_config(flow_id: str):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")

    flow = json.loads(fp.read_text(encoding="utf-8"))
    nodes = flow.get("flow_data", {}).get("drawflow", {}).get("Home", {}).get("data", {})

    interface_config = None
    for nid, node in nodes.items():
        if node.get("name") == "ui_interface":
            interface_config = node.get("data", {})
            break

    if interface_config is None:
        interface_config = {"mode": "form", "title": flow.get("name", "App"), "description": "", "theme": "dark"}

    chat_history = []
    history_path = interface_config.get("chat_history_path", "")
    if history_path and Path(history_path).exists():
        try:
            raw = json.loads(Path(history_path).read_text(encoding="utf-8"))
            if isinstance(raw, list):
                chat_history = raw
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "flow_id": flow_id,
        "flow_name": flow.get("name", "Untitled"),
        "interface": interface_config,
        "chat_history": chat_history,
    }


@app.post("/api/app/{flow_id}/run")
async def app_run(flow_id: str, body: dict):
    fp = FLOWS_DIR / f"{flow_id}.json"
    if not fp.exists():
        raise HTTPException(404, "Flow not found")

    flow = json.loads(fp.read_text(encoding="utf-8"))
    flow_data = flow["flow_data"]
    user_input = body.get("input", "")
    user_fields = body.get("fields")  # structured form data

    nodes = flow_data.get("drawflow", {}).get("Home", {}).get("data", {})
    for nid, node in nodes.items():
        if node.get("name") == "start":
            node["data"]["input_text"] = user_input
            break

    settings = _load_settings()
    from engine.executor import FlowExecutor
    executor = FlowExecutor(flow_data, settings)
    events: list[dict] = []

    async def capture(event: dict) -> None:
        events.append(event)

    try:
        await executor.execute(progress_callback=capture)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    interface_config = {}
    for nid, node in nodes.items():
        if node.get("name") == "ui_interface":
            interface_config = node.get("data", {})
            break

    output_key = interface_config.get("output_node_key", "")
    results = executor.results

    # Build serializable results (node_name + id as keys)
    named_results = {}
    for nid, node in nodes.items():
        key = node.get("name", "node") + "_" + nid
        if key in results:
            named_results[key] = results[key]

    if output_key and output_key in results:
        response_text = results[output_key]
    elif results:
        response_text = list(results.values())[-1]
    else:
        response_text = ""

    stream_chunks = [e.get("chunk", "") for e in events if e.get("type") == "node_output"]

    if settings.get("consolidate_memory_after_chat"):
        asyncio.create_task(_memory_consolidation_background(settings))

    return {
        "ok": True,
        "response": response_text,
        "results": {**results, **named_results},
        "stream": "".join(stream_chunks),
    }


@app.post("/api/memory/consolidate")
async def memory_consolidate(body: dict = Body(default_factory=dict)):
    """Sift short-term chat (chat_history.json) into memory_layers, persona notes, and insight vectors."""
    settings = _load_settings()
    report = await consolidate_short_term_to_long_term(
        settings,
        chat_path=body.get("chat_path", "assistant/chat_history.json"),
        memory_layers_path=body.get("memory_layers_path", "assistant/memory_layers.json"),
        persona_path=body.get("persona_path", "assistant/persona.json"),
        max_transcript_messages=int(body.get("max_transcript_messages", 48)),
        embed_insights=bool(body.get("embed_insights", True)),
        dry_run=bool(body.get("dry_run", False)),
    )
    return report


# ------------------------------------------------------------------
# Provider Test
# ------------------------------------------------------------------

@app.post("/api/test-provider")
async def test_provider(body: dict):
    settings = _load_settings()
    provider_type = body.get("provider", "openai")
    model = body.get("model") or settings.get("default_model")
    ollama_url = body.get("ollama_url") or settings.get("ollama_base_url")

    api_key = body.get("api_key", "")
    if isinstance(api_key, str) and api_key.startswith("*"):
        api_key = ""
    if not (isinstance(api_key, str) and api_key.strip()):
        if provider_type == "openai":
            api_key = settings.get("openai_api_key", "")
        elif provider_type == "anthropic":
            api_key = settings.get("anthropic_api_key", "")

    try:
        provider = create_provider(
            provider_type,
            api_key=api_key or None,
            model=model,
            base_url=ollama_url,
        )
        result = await provider.generate(
            system_prompt="You are a test assistant.",
            user_prompt="Say hello in exactly five words.",
            temperature=0.5,
            max_tokens=30,
        )
        return {"ok": True, "message": f"Success! Response: {result[:120]}"}
    except LLMError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        return {"ok": False, "message": f"Unexpected error: {exc}"}


# ------------------------------------------------------------------
# Agent IDE — assistant state readable & editable from the UI
# ------------------------------------------------------------------

ASSISTANT_DIR = Path("assistant")
VECTOR_DIR = Path("vector_stores")

_AGENT_DOC_PATHS: dict[str, Path] = {
    "persona": ASSISTANT_DIR / "persona.json",
    "memory_layers": ASSISTANT_DIR / "memory_layers.json",
    "chat_history": ASSISTANT_DIR / "chat_history.json",
}


@app.get("/api/agent-ide/overview")
async def agent_ide_overview():
    """Human-readable sections + stats for the Agent IDE panel."""
    sections: list[dict] = []
    stats: dict = {}

    pp = _AGENT_DOC_PATHS["persona"]
    if pp.exists():
        try:
            p = json.loads(pp.read_text(encoding="utf-8"))
            stats["persona"] = {
                "path": "assistant/persona.json",
                "name": p.get("name"),
                "conversation_count": p.get("conversation_count", 0),
                "relationship_notes_count": len(p.get("relationship_notes") or []),
            }
            pers = p.get("personality") or {}
            traits = pers.get("core_traits") or []
            lines: list[str] = [
                f"Name: {p.get('name', '—')}",
                f"Conversation number (stored counter): {p.get('conversation_count', 0)}",
                "",
                "Core traits:",
            ]
            for t in traits[:10]:
                lines.append(f"  • {t}")
            if len(traits) > 10:
                lines.append(f"  … (+{len(traits) - 10} more)")
            notes = p.get("relationship_notes") or []
            if notes:
                lines.extend(["", "Latest relationship notes (5):"])
                for n in notes[-5:]:
                    s = str(n)
                    lines.append(f"  – {s[:160]}{'…' if len(s) > 160 else ''}")
            sections.append({
                "title": "Persona",
                "subtitle": "assistant/persona.json — voice & soft notes",
                "body": "\n".join(lines),
            })
        except (json.JSONDecodeError, OSError):
            sections.append({
                "title": "Persona",
                "subtitle": "assistant/persona.json",
                "body": "(Could not read file)",
            })
    else:
        sections.append({
            "title": "Persona",
            "subtitle": "assistant/persona.json",
            "body": "(File not created yet — run the agent once or add it here.)",
        })

    mp = _AGENT_DOC_PATHS["memory_layers"]
    if mp.exists():
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
            uc = m.get("user_core") or {}
            stats["memory_layers"] = {
                "path": "assistant/memory_layers.json",
                "beliefs_count": len(m.get("atlas_core_beliefs") or []),
                "stable_facts_count": len(uc.get("stable_facts") or []),
                "boundaries_count": len(uc.get("boundaries") or []),
            }
            lines = ["Atlas core beliefs:"]
            for b in (m.get("atlas_core_beliefs") or [])[:8]:
                lines.append(f"  • {b}")
            lines.extend(["", "User core (durable file):"])
            lines.append(f"  Preferred name: {uc.get('preferred_name') or '—'}")
            lines.append(f"  Pronouns: {uc.get('pronouns') or '—'}")
            if uc.get("stable_facts"):
                lines.append("  Stable facts:")
                for f in (uc.get("stable_facts") or [])[-12:]:
                    lines.append(f"    – {f}")
            if uc.get("boundaries"):
                lines.append("  Boundaries:")
                for b in (uc.get("boundaries") or [])[-8:]:
                    lines.append(f"    – {b}")
            ws = (m.get("working_summary") or "").strip()
            lines.extend(["", f"Working summary: {ws or '—'}"])
            sections.append({
                "title": "Core memory layers",
                "subtitle": "assistant/memory_layers.json — beliefs & user core",
                "body": "\n".join(lines),
            })
        except (json.JSONDecodeError, OSError):
            sections.append({
                "title": "Core memory layers",
                "subtitle": "assistant/memory_layers.json",
                "body": "(Could not read file)",
            })
    else:
        sections.append({
            "title": "Core memory layers",
            "subtitle": "assistant/memory_layers.json",
            "body": "(File not created yet.)",
        })

    ch = _AGENT_DOC_PATHS["chat_history"]
    if ch.exists():
        try:
            msgs = json.loads(ch.read_text(encoding="utf-8"))
            if not isinstance(msgs, list):
                msgs = []
            stats["short_term"] = {
                "path": "assistant/chat_history.json",
                "message_count": len(msgs),
            }
            tail = msgs[-8:]
            lines = [
                f"Messages in sliding window file: {len(msgs)}",
                "",
                "Latest lines (truncated for preview):",
            ]
            for m in tail:
                role = m.get("role", "?")
                ts = m.get("ts", "")
                raw = str(m.get("content", ""))
                preview = raw[:160] + ("…" if len(raw) > 160 else "")
                lines.append(f"  [{role}]{f' @ {ts}' if ts else ''} {preview}")
            sections.append({
                "title": "Short-term chat",
                "subtitle": "assistant/chat_history.json — session thread",
                "body": "\n".join(lines),
            })
        except (json.JSONDecodeError, OSError):
            sections.append({
                "title": "Short-term chat",
                "body": "(Could not read file)",
            })
    else:
        sections.append({
            "title": "Short-term chat",
            "body": "(No chat_history.json yet.)",
        })

    vectors: list[dict] = []
    if VECTOR_DIR.exists():
        for fp in sorted(VECTOR_DIR.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                n = len(data) if isinstance(data, list) else 0
                vectors.append({
                    "collection": fp.stem,
                    "path": f"vector_stores/{fp.name}",
                    "chunks": n,
                })
            except (json.JSONDecodeError, OSError):
                vectors.append({
                    "collection": fp.stem,
                    "path": f"vector_stores/{fp.name}",
                    "chunks": None,
                })
    stats["vector_store_count"] = len(vectors)
    vbody = ["Semantic long-term (embedding chunks on disk):", ""]
    for v in vectors:
        c = v["chunks"]
        vbody.append(f"  • {v['collection']}: {c if c is not None else '?'} chunks — {v['path']}")
    sections.append({
        "title": "Vector stores",
        "subtitle": "vector_stores/*.json — RAG corpora",
        "body": "\n".join(vbody) if vectors else "No vector store files yet.",
    })

    sections.append({
        "title": "Also part of this agent (not shown as JSON cards)",
        "subtitle": "Engine & flow graph",
        "body": (
            "• Canvas flow definition: flows/<this-flow-id>.json (nodes, prompts, wiring).\n"
            "• Runtime: engine/executor.py, engine/embeddings.py, engine/memory_consolidation.py.\n"
            "• Optional logs: assistant/thought_journal.jsonl, assistant/consolidation_log.jsonl, assistant/conversation_log.md.\n"
            "• Model & keys: Settings (⚙)."
        ),
    })

    return {"stats": stats, "sections": sections}


@app.get("/api/agent-ide/chat-history")
async def agent_ide_chat_history(limit: int = 80):
    limit = min(max(int(limit), 1), 250)
    path = _AGENT_DOC_PATHS["chat_history"]
    if not path.exists():
        return {"messages": [], "total": 0}
    try:
        msgs = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(msgs, list):
            msgs = []
    except (json.JSONDecodeError, OSError):
        raise HTTPException(500, "Invalid chat_history.json")
    return {"messages": msgs[-limit:], "total": len(msgs)}


@app.get("/api/agent-ide/document/{name}")
async def agent_ide_get_document(name: str):
    if name not in ("persona", "memory_layers"):
        raise HTTPException(404, "Unknown document (editable: persona, memory_layers)")
    path = _AGENT_DOC_PATHS[name]
    if not path.exists():
        if name == "persona":
            return {
                "name": "Atlas",
                "tagline": "",
                "personality": {
                    "core_traits": [],
                    "speaking_style": "",
                    "values": "",
                    "quirks": [],
                },
                "relationship_notes": [],
                "learned_preferences": {},
                "conversation_count": 0,
            }
        return {
            "version": 1,
            "atlas_core_beliefs": [],
            "user_core": {
                "preferred_name": "",
                "pronouns": "",
                "stable_facts": [],
                "boundaries": [],
            },
            "working_summary": "",
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(500, "Invalid JSON")


@app.put("/api/agent-ide/document/{name}")
async def agent_ide_put_document(name: str, body: dict):
    if name not in ("persona", "memory_layers"):
        raise HTTPException(400, "Only persona and memory_layers can be saved from the IDE")
    path = _AGENT_DOC_PATHS[name]
    ASSISTANT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return {"ok": True}


# ------------------------------------------------------------------
# Static files (must be last so it doesn't shadow API routes)
# ------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _load_settings_file_raw() -> dict:
    """Contents of settings.json only (no environment overlay)."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_settings() -> dict:
    """Load settings with priority: environment variables > settings.json"""
    settings = dict(_load_settings_file_raw())

    settings["openai_api_key"] = os.environ.get("OPENAI_API_KEY") or settings.get("openai_api_key", "")
    settings["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY") or settings.get("anthropic_api_key", "")
    settings["ollama_base_url"] = os.environ.get("OLLAMA_BASE_URL") or settings.get("ollama_base_url", "http://localhost:11434")
    settings["default_provider"] = os.environ.get("DEFAULT_PROVIDER") or settings.get("default_provider", "openai")
    settings["default_model"] = os.environ.get("DEFAULT_MODEL") or settings.get("default_model", "gpt-4o")

    return settings


def _mask_key(key: str) -> str:
    if not key or len(key) <= 4:
        return key
    return "*" * (len(key) - 4) + key[-4:]


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)
