from __future__ import annotations

import io
import json
import zipfile


def export_flow(flow_data: dict, flow_name: str, settings: dict) -> bytes:
    """Export a flow as a self-contained ZIP archive."""
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in flow_name)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{safe_name}/config.json", _build_config(flow_data, flow_name))
        zf.writestr(f"{safe_name}/requirements.txt", _build_requirements())
        zf.writestr(f"{safe_name}/run.py", _build_run_py())
        zf.writestr(f"{safe_name}/runner.html", _build_runner_html(flow_name, flow_data))
        zf.writestr(f"{safe_name}/README.md", _build_readme(safe_name))
        zf.writestr(f"{safe_name}/.env.example", _build_env_example())

    return buf.getvalue()


# ------------------------------------------------------------------
# File generators
# ------------------------------------------------------------------

def _build_config(flow_data: dict, flow_name: str) -> str:
    config = {
        "name": flow_name,
        "flow_data": flow_data,
    }
    return json.dumps(config, indent=2)


def _build_requirements() -> str:
    return "\n".join([
        "fastapi",
        "uvicorn",
        "openai",
        "anthropic",
        "httpx",
        "websockets",
        "python-dotenv",
        "",
    ])


def _build_readme(safe_name: str) -> str:
    return f"""# {safe_name}

Exported from **Agent Flow Studio**.

## Setup

```bash
cd {safe_name}
pip install -r requirements.txt
```

## Environment Variables

Set the API keys for whichever LLM provider your flow uses:

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OLLAMA_BASE_URL = "http://localhost:11434"

# Linux / macOS
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OLLAMA_BASE_URL="http://localhost:11434"
```

## Run

```bash
python run.py
```

Open **http://localhost:8765** in your browser to monitor and trigger the flow.

## Using a `.env` file (recommended)

1. Copy `.env.example` to `.env` in this folder.
2. Edit `.env` with your API keys and defaults.
3. Run `python run.py` — the runner loads `.env` automatically via `python-dotenv`.
"""


def _build_env_example() -> str:
    return """# Copy this file to .env and fill in your values.

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
"""


def _build_run_py() -> str:
    return r'''#!/usr/bin/env python3
"""Standalone runner for an Agent Flow Studio workflow."""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# LLM Providers (embedded for portability)
# ---------------------------------------------------------------------------

class LLMError(Exception):
    pass


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_stream(self, system_prompt, user_prompt, temperature=0.7, max_tokens=1024):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        try:
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens, stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise LLMError(f"OpenAI error: {e}") from e


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate_stream(self, system_prompt, user_prompt, temperature=0.7, max_tokens=1024):
        kwargs = {
            "model": self.model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            raise LLMError(f"Anthropic error: {e}") from e


class OllamaProvider:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate_stream(self, system_prompt, user_prompt, temperature=0.7, max_tokens=1024):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True,
                           "options": {"temperature": temperature, "num_predict": max_tokens}},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
        except Exception as e:
            raise LLMError(f"Ollama error: {e}") from e


def _create_provider(provider_type, api_key=None, model=None, base_url=None):
    pt = (provider_type or "").lower()
    if pt == "openai":
        return OpenAIProvider(api_key=api_key or "", model=model or "gpt-4o")
    if pt == "anthropic":
        return AnthropicProvider(api_key=api_key or "", model=model or "claude-sonnet-4-20250514")
    if pt == "ollama":
        return OllamaProvider(base_url=base_url or "http://localhost:11434", model=model or "llama3")
    raise LLMError(f"Unknown provider: {provider_type}")


# ---------------------------------------------------------------------------
# Flow Executor (embedded)
# ---------------------------------------------------------------------------

from collections import defaultdict, deque


class FlowExecutor:
    def __init__(self, flow_data, settings):
        self.settings = settings
        self.nodes = {}
        self.node_outputs = {}
        self.results = {}
        raw = flow_data.get("drawflow", {}).get("Home", {}).get("data", {})
        for nid, node in raw.items():
            self.nodes[str(nid)] = node

    async def execute(self, progress_callback=None):
        flow_start = time.time()

        async def emit(evt):
            if progress_callback:
                await progress_callback(evt)

        try:
            order = self._topo_sort()
        except ValueError as e:
            await emit({"type": "flow_error", "error": str(e)})
            return

        try:
            for nid in order:
                node = self.nodes[nid]
                ntype = node.get("name", "")
                ndata = node.get("data", {})
                label = ndata.get("label", ntype)

                inputs = self._gather_inputs(node)
                has_conns = any(p.get("connections") for p in node.get("inputs", {}).values())
                if has_conns and not inputs:
                    continue

                await emit({"type": "node_start", "node_id": nid, "node_name": label, "node_type": ntype})
                ns = time.time()
                input_text = inputs[0] if inputs else ""

                retry_count = int(ndata.get("retry_count", 0))
                retry_delay = int(ndata.get("retry_delay_ms", 1000))
                on_error = ndata.get("on_error", "stop")

                last_err = None
                for attempt in range(retry_count + 1):
                    try:
                        if ntype == "start":
                            output = ndata.get("input_text", "")
                        elif ntype == "llm":
                            output = await self._exec_llm(nid, ndata, input_text, emit)
                        elif ntype == "prompt_template":
                            output = ndata.get("template", "{{input}}").replace("{{input}}", input_text)
                        elif ntype == "conditional":
                            matched = self._check_cond(ndata, input_text)
                            port = "output_1" if matched else "output_2"
                            self.node_outputs[(nid, port)] = input_text
                            await emit({"type": "node_complete", "node_id": nid,
                                        "output": f"Condition {'matched' if matched else 'failed'} -> {port}",
                                        "duration_ms": int((time.time() - ns) * 1000)})
                            last_err = None
                            break
                        elif ntype == "output":
                            oname = ndata.get("output_name", f"output_{nid}")
                            self.results[oname] = input_text
                            output = input_text
                        elif ntype == "code":
                            output = self._exec_code(ndata, input_text)
                        elif ntype == "merge":
                            mode = ndata.get("merge_mode", "concatenate")
                            sep = ndata.get("separator", "\n")
                            output = json.dumps(inputs) if mode == "json_array" else sep.join(inputs)
                        elif ntype == "shell":
                            output = await self._exec_shell(nid, ndata, input_text, emit)
                        elif ntype == "http_request":
                            output = await self._exec_http(ndata, input_text)
                        elif ntype == "file_read":
                            fp = ndata.get("file_path_template", "").replace("{{input}}", input_text).strip()
                            output = Path(fp).read_text(encoding="utf-8")
                        elif ntype == "file_write":
                            fp = ndata.get("file_path", "").strip()
                            Path(fp).parent.mkdir(parents=True, exist_ok=True)
                            wm = ndata.get("write_mode", "write")
                            if wm == "append":
                                with open(fp, "a", encoding="utf-8") as f: f.write(input_text)
                            else:
                                Path(fp).write_text(input_text, encoding="utf-8")
                            output = input_text
                        elif ntype == "loop":
                            output = await self._exec_loop(nid, ndata, input_text, emit)
                            last_err = None
                            break
                        elif ntype == "hitl":
                            await emit({"type": "node_output", "node_id": nid,
                                        "chunk": "[HITL] Auto-approved in standalone mode\n"})
                            self.node_outputs[(nid, "output_1")] = input_text
                            output = input_text
                            last_err = None
                            break
                        else:
                            output = input_text

                        if ntype not in ("conditional", "loop", "hitl"):
                            self.node_outputs[(nid, "output_1")] = output
                            await emit({"type": "node_complete", "node_id": nid,
                                        "output": (output or "")[:500],
                                        "duration_ms": int((time.time() - ns) * 1000)})
                        last_err = None
                        break

                    except Exception as exc:
                        last_err = exc
                        if attempt < retry_count:
                            await emit({"type": "node_output", "node_id": nid,
                                        "chunk": f"[retry {attempt+1}/{retry_count}] {exc}\n"})
                            await asyncio.sleep(retry_delay / 1000)

                if last_err is not None:
                    if on_error == "continue":
                        self.node_outputs[(nid, "output_1")] = ""
                        await emit({"type": "node_error", "node_id": nid, "error": f"(continued) {last_err}"})
                    elif on_error == "output_error":
                        err_json = json.dumps({"error": str(last_err), "input": input_text[:200]})
                        self.node_outputs[(nid, "output_1")] = err_json
                        await emit({"type": "node_error", "node_id": nid, "error": f"(output_error) {last_err}"})
                    else:
                        await emit({"type": "node_error", "node_id": nid, "error": str(last_err)})

            await emit({"type": "flow_complete",
                        "duration_ms": int((time.time() - flow_start) * 1000),
                        "results": self.results})
        except Exception as exc:
            await emit({"type": "flow_error", "error": str(exc)})

    async def _exec_llm(self, nid, ndata, input_text, emit):
        pt = ndata.get("provider", self.settings.get("default_provider", "openai"))
        model = ndata.get("model") or self.settings.get("default_model")
        api_key = self._api_key(pt)
        base_url = self.settings.get("ollama_base_url")
        prov = _create_provider(pt, api_key=api_key, model=model, base_url=base_url)

        user_prompt = ndata.get("user_prompt_template", "{{input}}").replace("{{input}}", input_text)
        sys_prompt = ndata.get("system_prompt", "")
        temp = float(ndata.get("temperature", 0.7))
        mt = int(ndata.get("max_tokens", 1024))
        full = ""
        async for chunk in prov.generate_stream(sys_prompt, user_prompt, temp, mt):
            full += chunk
            await emit({"type": "node_output", "node_id": nid, "chunk": chunk})
        return full

    def _check_cond(self, ndata, text):
        ct = ndata.get("condition_type", "contains")
        cv = ndata.get("condition_value", "")
        if ct == "contains": return cv in text
        if ct == "not_contains": return cv not in text
        if ct == "equals": return text == cv
        if ct == "not_equals": return text != cv
        if ct == "starts_with": return text.startswith(cv)
        if ct == "ends_with": return text.endswith(cv)
        if ct == "regex": return bool(re.search(cv, text))
        return False

    async def _exec_shell(self, nid, ndata, input_text, emit):
        cmd = ndata.get("command_template", "").replace("{{input}}", input_text)
        st = ndata.get("shell_type", "powershell")
        to = int(ndata.get("timeout", 30))
        cwd = ndata.get("working_directory", "").strip() or None
        if st == "python": args = ["python", "-c", cmd]
        elif st == "bash": args = ["bash", "-c", cmd]
        else: args = ["powershell", "-NoProfile", "-Command", cmd]
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE, cwd=cwd)
        try:
            so, se = await asyncio.wait_for(proc.communicate(input=input_text.encode()), timeout=to)
        except asyncio.TimeoutError:
            proc.kill(); raise ValueError(f"Shell timed out after {to}s")
        stdout = so.decode("utf-8", errors="replace")
        if stdout: await emit({"type": "node_output", "node_id": nid, "chunk": stdout})
        if proc.returncode != 0:
            raise ValueError(f"Shell exit {proc.returncode}: {se.decode('utf-8', errors='replace')[:300]}")
        return stdout.strip()

    @staticmethod
    async def _exec_http(ndata, input_text):
        method = ndata.get("method", "GET").upper()
        url = ndata.get("url_template", "").replace("{{input}}", input_text)
        hdr_raw = ndata.get("headers_json", "").strip()
        headers = json.loads(hdr_raw) if hdr_raw else {}
        body = None
        if method in ("POST", "PUT", "PATCH"):
            bt = ndata.get("body_template", "")
            if bt: body = bt.replace("{{input}}", input_text)
        async with httpx.AsyncClient(timeout=float(ndata.get("timeout", 30))) as cl:
            r = await cl.request(method, url, headers=headers, content=body)
            r.raise_for_status()
        ep = ndata.get("extract_path", "").strip()
        if ep:
            try:
                d = r.json()
                for k in ep.split("."):
                    if k.endswith("]"):
                        b, i = k[:-1].split("["); d = d[b][int(i)]
                    else: d = d[k]
                return str(d)
            except Exception: pass
        return r.text

    @staticmethod
    def _exec_code(ndata, input_text):
        code = ndata.get("code", "output = input_data")
        unrestricted = ndata.get("unrestricted", False)
        ns = {"input_data": input_text}
        if unrestricted:
            import builtins
            exec(code, {"__builtins__": builtins, "json": json, "os": os, "re": re, "Path": Path}, ns)
            return str(ns.get("output", ""))
        safe = {
            "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
            "type": type, "print": print, "json": json,
            "True": True, "False": False, "None": None,
        }
        ns = {"input_data": input_text}
        exec(code, {"__builtins__": safe}, ns)
        return str(ns.get("output", ""))

    async def _exec_loop(self, nid, ndata, input_text, emit):
        max_iter = int(ndata.get("max_iterations", 5))
        cond_type = ndata.get("condition_type", "contains")
        cond_value = ndata.get("condition_value", "")
        loop_mode = ndata.get("loop_mode", "code")
        delay_ms = int(ndata.get("loop_delay_ms", 0))
        current = input_text
        for i in range(max_iter):
            await emit({"type": "node_output", "node_id": nid, "chunk": f"[iter {i+1}/{max_iter}] "})
            if loop_mode == "code":
                code = ndata.get("loop_code", "output = input_data")
                ns = {"input_data": current, "iteration": i}
                unrestricted = ndata.get("unrestricted", False)
                if unrestricted:
                    import builtins
                    exec(code, {"__builtins__": builtins, "json": json, "os": os, "re": re, "Path": Path}, ns)
                else:
                    safe = {"len":len,"str":str,"int":int,"float":float,"bool":bool,"list":list,"dict":dict,
                            "tuple":tuple,"set":set,"range":range,"enumerate":enumerate,"zip":zip,
                            "min":min,"max":max,"sum":sum,"abs":abs,"round":round,"sorted":sorted,
                            "reversed":reversed,"isinstance":isinstance,"type":type,"print":print,
                            "json":json,"True":True,"False":False,"None":None}
                    exec(code, {"__builtins__": safe}, ns)
                current = str(ns.get("output", ""))
            elif loop_mode == "llm":
                pt = ndata.get("loop_provider","") or self.settings.get("default_provider","openai")
                model = ndata.get("loop_model","") or self.settings.get("default_model")
                api_key = self._api_key(pt)
                prov = _create_provider(pt, api_key=api_key, model=model, base_url=self.settings.get("ollama_base_url"))
                sys_p = ndata.get("loop_system_prompt","")
                user_p = ndata.get("loop_user_template","{{input}}").replace("{{input}}",current).replace("{{iteration}}",str(i))
                full=""
                async for ch in prov.generate_stream(sys_p, user_p, float(ndata.get("loop_temperature",0.7)), int(ndata.get("loop_max_tokens",1024))):
                    full+=ch
                    await emit({"type":"node_output","node_id":nid,"chunk":ch})
                current=full
            elif loop_mode == "shell":
                cmd = ndata.get("loop_command","").replace("{{input}}",current).replace("{{iteration}}",str(i))
                st = ndata.get("loop_shell_type","powershell")
                if st=="python": args=["python","-c",cmd]
                elif st=="bash": args=["bash","-c",cmd]
                else: args=["powershell","-NoProfile","-Command",cmd]
                proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE)
                so,se = await asyncio.wait_for(proc.communicate(input=current.encode()), timeout=30)
                current = so.decode("utf-8", errors="replace").strip()
                await emit({"type":"node_output","node_id":nid,"chunk":current[:200]+"\n"})
            matched = self._check_cond({"condition_type":cond_type,"condition_value":cond_value}, current)
            if matched:
                self.node_outputs[(nid,"output_1")] = current
                await emit({"type":"node_complete","node_id":nid,"output":f"Condition met after {i+1} iters","duration_ms":0})
                return current
            if delay_ms > 0 and i < max_iter-1:
                await asyncio.sleep(delay_ms/1000)
        self.node_outputs[(nid,"output_2")] = current
        await emit({"type":"node_complete","node_id":nid,"output":f"Max iterations ({max_iter}) reached -> output_2","duration_ms":0})
        return current

    def _topo_sort(self):
        graph = defaultdict(list)
        indeg = defaultdict(int)
        ids = set(self.nodes.keys())
        for nid, node in self.nodes.items():
            for port in node.get("outputs", {}).values():
                for c in port.get("connections", []):
                    t = str(c["node"])
                    graph[nid].append(t)
                    indeg[t] += 1
        q = deque(n for n in ids if indeg.get(n, 0) == 0)
        out = []
        while q:
            n = q.popleft()
            out.append(n)
            for d in graph[n]:
                indeg[d] -= 1
                if indeg[d] == 0:
                    q.append(d)
        if len(out) != len(ids):
            raise ValueError("Flow contains a cycle")
        return out

    def _gather_inputs(self, node):
        vals = []
        for pname in sorted(node.get("inputs", {}).keys()):
            for c in node["inputs"][pname].get("connections", []):
                key = (str(c["node"]), c.get("input", "output_1"))
                if key in self.node_outputs:
                    vals.append(self.node_outputs[key])
        return vals

    def _api_key(self, pt):
        pt = (pt or "").lower()
        if pt == "openai": return self.settings.get("openai_api_key", "")
        if pt == "anthropic": return self.settings.get("anthropic_api_key", "")
        return None


# ---------------------------------------------------------------------------
# FastAPI Server
# ---------------------------------------------------------------------------

app = FastAPI(title="Agent Flow Runner")

CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))
FLOW_DATA = CONFIG["flow_data"]
FLOW_NAME = CONFIG.get("name", "Workflow")


@app.get("/", response_class=HTMLResponse)
async def root():
    return Path("runner.html").read_text(encoding="utf-8")


@app.post("/run")
async def run_flow():
    settings = {
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    }
    executor = FlowExecutor(FLOW_DATA, settings)
    events = []

    async def collect(evt):
        events.append(evt)

    await executor.execute(progress_callback=collect)
    return {"events": events, "results": executor.results}


@app.websocket("/ws")
async def ws_execute(ws: WebSocket):
    await ws.accept()
    settings = {
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    }
    executor = FlowExecutor(FLOW_DATA, settings)

    async def send_event(evt):
        await ws.send_text(json.dumps(evt))

    try:
        await executor.execute(progress_callback=send_event)
    except Exception as exc:
        await ws.send_text(json.dumps({"type": "flow_error", "error": str(exc)}))
    finally:
        await ws.close()


if __name__ == "__main__":
    import uvicorn
    print(f"Starting runner for '{FLOW_NAME}' on http://localhost:8765")
    uvicorn.run(app, host="0.0.0.0", port=8765)
'''


def _build_runner_html(flow_name: str, flow_data: dict) -> str:
    nodes = flow_data.get("drawflow", {}).get("Home", {}).get("data", {})
    node_list_items = ""
    for nid in sorted(nodes.keys(), key=lambda x: int(x)):
        node = nodes[nid]
        label = node.get("data", {}).get("label", node.get("name", f"Node {nid}"))
        ntype = node.get("name", "unknown")
        node_list_items += (
            f'        <div class="node-item" id="node-{nid}">'
            f'<span class="node-type">{ntype}</span> '
            f'<span class="node-label">{label}</span>'
            f'<span class="node-status" id="status-{nid}"></span>'
            f'</div>\n'
        )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{flow_name} - Agent Flow Runner</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f0f1a; color: #e0e0e0; min-height: 100vh;
    display: flex; flex-direction: column;
  }}
  header {{
    background: #1a1a2e; padding: 1.25rem 2rem;
    border-bottom: 1px solid #2a2a4a;
    display: flex; align-items: center; justify-content: space-between;
  }}
  header h1 {{ font-size: 1.4rem; color: #7c83ff; }}
  header .subtitle {{ font-size: 0.85rem; color: #888; }}
  .container {{ display: flex; flex: 1; overflow: hidden; }}
  .panel {{ padding: 1.5rem; overflow-y: auto; }}
  .left {{ width: 320px; border-right: 1px solid #2a2a4a; background: #12122a; }}
  .right {{ flex: 1; display: flex; flex-direction: column; }}
  h2 {{ font-size: 1rem; margin-bottom: 1rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; }}
  .node-item {{
    padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; border-radius: 6px;
    background: #1a1a2e; border: 1px solid #2a2a4a; font-size: 0.85rem;
    display: flex; align-items: center; gap: 0.5rem; transition: border-color 0.2s;
  }}
  .node-item.active {{ border-color: #7c83ff; background: #1e1e3a; }}
  .node-item.done {{ border-color: #4caf50; }}
  .node-item.error {{ border-color: #f44336; }}
  .node-type {{
    background: #2a2a4a; padding: 0.15rem 0.5rem; border-radius: 4px;
    font-size: 0.75rem; color: #7c83ff; font-weight: 600; text-transform: uppercase;
    flex-shrink: 0;
  }}
  .node-label {{ flex: 1; }}
  .node-status {{ font-size: 0.75rem; color: #888; flex-shrink: 0; }}
  #run-btn {{
    width: 100%; padding: 0.75rem; margin-top: 1rem;
    background: #7c83ff; border: none; border-radius: 6px;
    color: #fff; font-size: 0.95rem; font-weight: 600; cursor: pointer;
    transition: background 0.2s;
  }}
  #run-btn:hover {{ background: #6a70e0; }}
  #run-btn:disabled {{ background: #444; cursor: not-allowed; }}
  .log-area {{
    flex: 1; padding: 1.5rem; overflow-y: auto; font-family: "Fira Code", monospace;
    font-size: 0.82rem; line-height: 1.6; background: #0a0a15;
  }}
  .log-entry {{ margin-bottom: 0.25rem; }}
  .log-entry.info {{ color: #7c83ff; }}
  .log-entry.output {{ color: #81c784; }}
  .log-entry.error {{ color: #f44336; }}
  .log-entry.complete {{ color: #ffd54f; }}
  .results-area {{
    padding: 1rem 1.5rem; border-top: 1px solid #2a2a4a;
    background: #12122a; max-height: 200px; overflow-y: auto;
  }}
  .results-area pre {{ font-size: 0.82rem; white-space: pre-wrap; color: #81c784; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>{flow_name}</h1>
    <div class="subtitle">Agent Flow Runner</div>
  </div>
</header>
<div class="container">
  <div class="panel left">
    <h2>Nodes</h2>
{node_list_items}
    <button id="run-btn" onclick="runFlow()">Run Flow</button>
  </div>
  <div class="right">
    <div class="log-area" id="log"></div>
    <div class="results-area" id="results" style="display:none;">
      <h2>Results</h2>
      <pre id="results-content"></pre>
    </div>
  </div>
</div>
<script>
function addLog(msg, cls) {{
  const el = document.getElementById("log");
  const d = document.createElement("div");
  d.className = "log-entry " + (cls || "");
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}}

function runFlow() {{
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  btn.textContent = "Running...";
  document.getElementById("log").innerHTML = "";
  document.getElementById("results").style.display = "none";
  document.querySelectorAll(".node-item").forEach(n => n.className = "node-item");

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(proto + "//" + location.host + "/ws");

  ws.onmessage = function(e) {{
    const evt = JSON.parse(e.data);
    if (evt.type === "node_start") {{
      addLog("\\u25b6 " + evt.node_name + " (" + evt.node_type + ")", "info");
      const el = document.getElementById("node-" + evt.node_id);
      if (el) el.className = "node-item active";
    }} else if (evt.type === "node_output") {{
      addLog("  " + evt.chunk, "output");
    }} else if (evt.type === "node_complete") {{
      addLog("\\u2713 " + evt.node_id + " done in " + evt.duration_ms + "ms", "info");
      const el = document.getElementById("node-" + evt.node_id);
      if (el) el.className = "node-item done";
      const st = document.getElementById("status-" + evt.node_id);
      if (st) st.textContent = evt.duration_ms + "ms";
    }} else if (evt.type === "node_error") {{
      addLog("\\u2717 Error at " + evt.node_id + ": " + evt.error, "error");
      const el = document.getElementById("node-" + evt.node_id);
      if (el) el.className = "node-item error";
    }} else if (evt.type === "flow_complete") {{
      addLog("\\n\\u2714 Flow complete in " + evt.duration_ms + "ms", "complete");
      document.getElementById("results").style.display = "block";
      document.getElementById("results-content").textContent = JSON.stringify(evt.results, null, 2);
      btn.disabled = false;
      btn.textContent = "Run Flow";
    }} else if (evt.type === "flow_error") {{
      addLog("\\u2717 Flow error: " + evt.error, "error");
      btn.disabled = false;
      btn.textContent = "Run Flow";
    }}
  }};

  ws.onerror = function() {{
    addLog("WebSocket connection error", "error");
    btn.disabled = false;
    btn.textContent = "Run Flow";
  }};
}}
</script>
</body>
</html>'''


def _build_env_example() -> str:
    return """# Agent Flow Studio - Environment Variables
# Copy this file to .env and fill in your values

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Ollama Configuration (for local models)
OLLAMA_BASE_URL=http://localhost:11434

# Default Provider: openai, anthropic, or ollama
DEFAULT_PROVIDER=openai

# Default Model (depends on provider)
# OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo
# Anthropic: claude-3-5-sonnet-20241022, claude-3-opus-20240229
# Ollama: llama3, mistral, codellama, etc.
DEFAULT_MODEL=gpt-4o
"""
