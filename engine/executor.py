from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx

from engine.embeddings import VectorStore, get_embeddings
from engine.llm_providers import LLMError, create_provider

Emit = Callable[[dict], Coroutine[Any, Any, None]]


class FlowExecutor:
    """Executes an agent workflow defined in Drawflow export format."""

    def __init__(self, flow_data: dict, settings: dict):
        self.flow_data = flow_data
        self.settings = settings
        self.nodes: dict[str, dict] = {}
        self.node_outputs: dict[tuple[str, str], str] = {}
        self.results: dict[str, str] = {}
        self.hitl_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._cancelled = False
        self._conversation_stores: dict[str, list[dict]] = {}

        raw = flow_data.get("drawflow", {}).get("Home", {}).get("data", {})
        for nid, node in raw.items():
            self.nodes[str(nid)] = node

    async def submit_hitl_response(self, node_id: str, action: str, data: str) -> None:
        await self.hitl_queue.put({"node_id": node_id, "action": action, "data": data})

    def cancel(self) -> None:
        self._cancelled = True

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    async def execute(self, progress_callback: Emit | None = None) -> None:
        flow_start = time.time()

        async def _emit(event: dict) -> None:
            if progress_callback:
                await progress_callback(event)

        try:
            sorted_ids = self._topological_sort()
        except ValueError as exc:
            await _emit({"type": "flow_error", "error": str(exc)})
            return

        try:
            for nid in sorted_ids:
                if self._cancelled:
                    await _emit({"type": "flow_error", "error": "Execution cancelled"})
                    return

                node = self.nodes[nid]
                node_type = node.get("name", "")
                node_data = node.get("data", {})
                node_label = node_data.get("label", node_type)

                inputs = self._gather_inputs(node)
                has_connected_inputs = any(
                    port.get("connections")
                    for port in node.get("inputs", {}).values()
                )
                if has_connected_inputs and not inputs:
                    continue

                await _emit({
                    "type": "node_start",
                    "node_id": nid,
                    "node_name": node_label,
                    "node_type": node_type,
                })

                node_start = time.time()
                input_text = inputs[0] if inputs else ""

                try:
                    output = await self._run_node_with_retry(
                        nid, node_type, node_data, input_text, inputs, _emit,
                    )

                    if node_type in ("conditional", "loop", "hitl"):
                        continue

                    self.node_outputs[(nid, "output_1")] = output
                    duration_ms = int((time.time() - node_start) * 1000)
                    await _emit({
                        "type": "node_complete",
                        "node_id": nid,
                        "output": (output or "")[:500],
                        "duration_ms": duration_ms,
                    })

                except Exception as exc:
                    on_error = node_data.get("on_error", "stop")

                    if on_error == "continue":
                        self.node_outputs[(nid, "output_1")] = ""
                        await _emit({
                            "type": "node_error_handled",
                            "node_id": nid,
                            "error": str(exc),
                            "action": "continue",
                        })
                    elif on_error == "output_error":
                        error_payload = json.dumps({"error": str(exc), "input": input_text[:200]})
                        self.node_outputs[(nid, "output_1")] = error_payload
                        await _emit({
                            "type": "node_error_handled",
                            "node_id": nid,
                            "error": str(exc),
                            "action": "output_error",
                        })
                    else:
                        await _emit({"type": "node_error", "node_id": nid, "error": str(exc)})

            total_ms = int((time.time() - flow_start) * 1000)
            await _emit({
                "type": "flow_complete",
                "duration_ms": total_ms,
                "results": self.results,
            })

        except Exception as exc:
            await _emit({"type": "flow_error", "error": str(exc)})

    # ------------------------------------------------------------------
    # Debug (step-through) execution
    # ------------------------------------------------------------------

    async def execute_debug(
        self,
        progress_callback: Emit | None = None,
        debug_signal: asyncio.Queue | None = None,
        breakpoints: set[str] | None = None,
    ) -> None:
        flow_start = time.time()
        if breakpoints is None:
            breakpoints = set()
        continue_mode = False

        async def _emit(event: dict) -> None:
            if progress_callback:
                await progress_callback(event)

        try:
            sorted_ids = self._topological_sort()
        except ValueError as exc:
            await _emit({"type": "flow_error", "error": str(exc)})
            return

        try:
            for nid in sorted_ids:
                if self._cancelled:
                    await _emit({"type": "flow_error", "error": "Execution cancelled"})
                    return

                node = self.nodes[nid]
                node_type = node.get("name", "")
                node_data = node.get("data", {})
                node_label = node_data.get("label", node_type)

                inputs = self._gather_inputs(node)
                has_connected_inputs = any(
                    port.get("connections")
                    for port in node.get("inputs", {}).values()
                )
                if has_connected_inputs and not inputs:
                    continue

                input_text = inputs[0] if inputs else ""

                should_pause = not continue_mode or nid in breakpoints
                if should_pause and debug_signal:
                    await _emit({
                        "type": "debug_pause",
                        "node_id": nid,
                        "node_name": node_label,
                        "node_type": node_type,
                        "input_data": input_text[:2000],
                        "all_inputs": [x[:500] for x in inputs],
                    })

                    signal = await debug_signal.get()
                    sig_type = signal.get("type", "")

                    if sig_type == "debug_stop":
                        await _emit({"type": "flow_error", "error": "Debug stopped by user"})
                        return

                    if sig_type == "debug_edit":
                        input_text = signal.get("input_data", input_text)
                        if inputs:
                            inputs[0] = input_text

                    if sig_type == "debug_continue":
                        continue_mode = True
                        bps = signal.get("breakpoints", [])
                        if bps:
                            breakpoints = set(str(b) for b in bps)

                await _emit({
                    "type": "node_start",
                    "node_id": nid,
                    "node_name": node_label,
                    "node_type": node_type,
                })

                node_start = time.time()

                try:
                    output = await self._run_node_with_retry(
                        nid, node_type, node_data, input_text, inputs, _emit,
                    )

                    if node_type in ("conditional", "loop", "hitl"):
                        continue

                    self.node_outputs[(nid, "output_1")] = output
                    duration_ms = int((time.time() - node_start) * 1000)
                    await _emit({
                        "type": "node_complete",
                        "node_id": nid,
                        "output": (output or "")[:500],
                        "duration_ms": duration_ms,
                    })

                except Exception as exc:
                    on_error = node_data.get("on_error", "stop")
                    if on_error == "continue":
                        self.node_outputs[(nid, "output_1")] = ""
                        await _emit({
                            "type": "node_error_handled",
                            "node_id": nid,
                            "error": str(exc),
                            "action": "continue",
                        })
                    elif on_error == "output_error":
                        error_payload = json.dumps({"error": str(exc), "input": input_text[:200]})
                        self.node_outputs[(nid, "output_1")] = error_payload
                        await _emit({
                            "type": "node_error_handled",
                            "node_id": nid,
                            "error": str(exc),
                            "action": "output_error",
                        })
                    else:
                        await _emit({"type": "node_error", "node_id": nid, "error": str(exc)})

            total_ms = int((time.time() - flow_start) * 1000)
            await _emit({
                "type": "flow_complete",
                "duration_ms": total_ms,
                "results": self.results,
            })

        except Exception as exc:
            await _emit({"type": "flow_error", "error": str(exc)})

    # ------------------------------------------------------------------
    # Retry wrapper
    # ------------------------------------------------------------------

    async def _run_node_with_retry(
        self, nid: str, node_type: str, node_data: dict,
        input_text: str, all_inputs: list[str], emit: Emit,
    ) -> str:
        retry_count = int(node_data.get("retry_count", 0))
        retry_delay = int(node_data.get("retry_delay_ms", 1000))
        last_error: Exception | None = None

        for attempt in range(retry_count + 1):
            try:
                return await self._run_node(nid, node_type, node_data, input_text, all_inputs, emit)
            except Exception as exc:
                last_error = exc
                if attempt < retry_count:
                    await emit({
                        "type": "node_output",
                        "node_id": nid,
                        "chunk": f"[retry {attempt + 1}/{retry_count}] {exc}\n",
                    })
                    await asyncio.sleep(retry_delay / 1000)

        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Node dispatch
    # ------------------------------------------------------------------

    async def _run_node(
        self, nid: str, node_type: str, node_data: dict,
        input_text: str, all_inputs: list[str], emit: Emit,
    ) -> str:
        if node_type == "start":
            return node_data.get("input_text", "")
        if node_type == "llm":
            return await self._exec_llm(nid, node_data, input_text, emit)
        if node_type == "prompt_template":
            return self._exec_prompt_template(node_data, input_text, all_inputs)
        if node_type == "conditional":
            return await self._exec_conditional(nid, node_data, input_text, emit)
        if node_type == "output":
            name = node_data.get("output_name", f"output_{nid}")
            self.results[name] = input_text
            return input_text
        if node_type == "code":
            return self._exec_code(node_data, input_text)
        if node_type == "merge":
            return self._exec_merge(node_data, all_inputs)
        if node_type == "shell":
            return await self._exec_shell(nid, node_data, input_text, emit)
        if node_type == "http_request":
            return await self._exec_http(node_data, input_text)
        if node_type == "file_read":
            return self._exec_file_read(node_data, input_text)
        if node_type == "file_write":
            return self._exec_file_write(node_data, input_text)
        if node_type == "loop":
            return await self._exec_loop(nid, node_data, input_text, emit)
        if node_type == "hitl":
            return await self._exec_hitl(nid, node_data, input_text, emit)
        if node_type == "react_agent":
            return await self._exec_react_agent(nid, node_data, input_text, emit)
        if node_type == "conversation_memory":
            return self._exec_conversation_memory(nid, node_data, input_text)
        if node_type == "map_reduce":
            return await self._exec_map_reduce(nid, node_data, input_text, emit)
        if node_type == "embed":
            return await self._exec_embed(nid, node_data, input_text, emit)
        if node_type == "vector_store":
            return await self._exec_vector_store(nid, node_data, input_text, emit)
        if node_type == "rag_retrieve":
            return await self._exec_rag_retrieve(nid, node_data, input_text, emit)
        return input_text

    # ------------------------------------------------------------------
    # Loop node
    # ------------------------------------------------------------------

    async def _exec_loop(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        max_iter = int(node_data.get("max_iterations", 5))
        cond_type = node_data.get("condition_type", "contains")
        cond_value = node_data.get("condition_value", "")
        loop_mode = node_data.get("loop_mode", "code")
        delay_ms = int(node_data.get("loop_delay_ms", 0))
        current = input_text

        for i in range(max_iter):
            if self._cancelled:
                raise ValueError("Loop cancelled")

            await emit({"type": "node_output", "node_id": nid, "chunk": f"[iter {i + 1}/{max_iter}] "})

            if loop_mode == "code":
                code = node_data.get("loop_code", "output = input_data")
                local_ns: dict[str, Any] = {"input_data": current, "iteration": i}
                unrestricted = node_data.get("unrestricted", False)
                if unrestricted:
                    import builtins
                    exec(code, {"__builtins__": builtins, "json": json, "os": os, "re": re, "Path": Path}, local_ns)
                else:
                    safe = {
                        "len": len, "str": str, "int": int, "float": float, "bool": bool,
                        "list": list, "dict": dict, "tuple": tuple, "set": set,
                        "range": range, "enumerate": enumerate, "zip": zip,
                        "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                        "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
                        "type": type, "print": print, "json": json,
                        "True": True, "False": False, "None": None,
                    }
                    exec(code, {"__builtins__": safe}, local_ns)
                current = str(local_ns.get("output", ""))

            elif loop_mode == "llm":
                provider_type = node_data.get("loop_provider", "") or self.settings.get("default_provider", "openai")
                model = node_data.get("loop_model", "") or self.settings.get("default_model")
                api_key = self._resolve_api_key(provider_type)
                provider = create_provider(provider_type, api_key=api_key, model=model, base_url=self.settings.get("ollama_base_url"))
                sys_prompt = node_data.get("loop_system_prompt", "")
                user_tpl = node_data.get("loop_user_template", "{{input}}")
                user_prompt = user_tpl.replace("{{input}}", current).replace("{{iteration}}", str(i))
                temp = float(node_data.get("loop_temperature", 0.7))
                mt = int(node_data.get("loop_max_tokens", 1024))
                full = ""
                async for chunk in provider.generate_stream(sys_prompt, user_prompt, temp, mt):
                    full += chunk
                    await emit({"type": "node_output", "node_id": nid, "chunk": chunk})
                current = full

            elif loop_mode == "shell":
                cmd = node_data.get("loop_command", "").replace("{{input}}", current).replace("{{iteration}}", str(i))
                shell_type = node_data.get("loop_shell_type", "powershell")
                if shell_type == "python":
                    args = ["python", "-c", cmd]
                elif shell_type == "bash":
                    args = ["bash", "-c", cmd]
                else:
                    args = ["powershell", "-NoProfile", "-Command", cmd]
                proc = await asyncio.create_subprocess_exec(
                    *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                )
                so, se = await asyncio.wait_for(proc.communicate(input=current.encode()), timeout=30)
                current = so.decode("utf-8", errors="replace").strip()
                await emit({"type": "node_output", "node_id": nid, "chunk": current[:200] + "\n"})

            matched = self._check_condition(cond_type, cond_value, current)
            if matched:
                self.node_outputs[(nid, "output_1")] = current
                await emit({
                    "type": "node_complete", "node_id": nid,
                    "output": f"Condition met after {i + 1} iterations",
                    "duration_ms": 0,
                })
                return current

            if delay_ms > 0 and i < max_iter - 1:
                await asyncio.sleep(delay_ms / 1000)

        self.node_outputs[(nid, "output_2")] = current
        await emit({
            "type": "node_complete", "node_id": nid,
            "output": f"Max iterations ({max_iter}) reached \u2192 output_2",
            "duration_ms": 0,
        })
        return current

    # ------------------------------------------------------------------
    # Human-in-the-loop
    # ------------------------------------------------------------------

    async def _exec_hitl(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        prompt = node_data.get("prompt_message", "Review and approve this data:")
        allow_edit = node_data.get("allow_edit", True)
        timeout_sec = int(node_data.get("timeout", 300))

        await emit({
            "type": "hitl_waiting",
            "node_id": nid,
            "prompt": prompt,
            "data": input_text,
            "allow_edit": allow_edit,
        })

        try:
            response = await asyncio.wait_for(self._wait_hitl(nid), timeout=timeout_sec)
        except asyncio.TimeoutError:
            self.node_outputs[(nid, "output_2")] = input_text
            await emit({
                "type": "node_complete", "node_id": nid,
                "output": "HITL timed out \u2192 rejected",
                "duration_ms": timeout_sec * 1000,
            })
            return input_text

        action = response.get("action", "reject")
        data = response.get("data", input_text)

        if action == "approve":
            self.node_outputs[(nid, "output_1")] = data
            await emit({
                "type": "node_complete", "node_id": nid,
                "output": f"Approved (data {'edited' if data != input_text else 'unchanged'})",
                "duration_ms": 0,
            })
        else:
            self.node_outputs[(nid, "output_2")] = input_text
            await emit({
                "type": "node_complete", "node_id": nid,
                "output": "Rejected \u2192 output_2",
                "duration_ms": 0,
            })

        return data

    async def _wait_hitl(self, node_id: str) -> dict:
        while True:
            msg = await self.hitl_queue.get()
            if msg.get("node_id") == node_id:
                return msg

    # ------------------------------------------------------------------
    # Prompt Template
    # ------------------------------------------------------------------

    def _exec_prompt_template(self, node_data: dict, input_text: str, all_inputs: list[str]) -> str:
        template = node_data.get("template", "{{input}}")

        template = template.replace("{{input}}", input_text)

        for i, inp in enumerate(all_inputs):
            template = template.replace(f"{{{{input_{i+1}}}}}", inp)

        try:
            data = json.loads(input_text)
            if isinstance(data, dict):
                for key, value in data.items():
                    placeholder = "{{" + str(key) + "}}"
                    if placeholder in template:
                        val_str = json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)
                        template = template.replace(placeholder, val_str)
        except (json.JSONDecodeError, TypeError):
            pass

        for i, inp in enumerate(all_inputs):
            try:
                data = json.loads(inp)
                if isinstance(data, dict):
                    for key, value in data.items():
                        placeholder = "{{" + str(key) + "}}"
                        if placeholder in template:
                            val_str = json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)
                            template = template.replace(placeholder, val_str)
            except (json.JSONDecodeError, TypeError):
                pass

        return template

    # ------------------------------------------------------------------
    # LLM execution with streaming
    # ------------------------------------------------------------------

    async def _exec_llm(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        provider_type = node_data.get("provider", "") or self.settings.get("default_provider", "openai")
        model = node_data.get("model") or self.settings.get("default_model")
        api_key = self._resolve_api_key(provider_type)
        base_url = self.settings.get("ollama_base_url")
        provider = create_provider(provider_type, api_key=api_key, model=model, base_url=base_url)
        user_prompt = node_data.get("user_prompt_template", "{{input}}").replace("{{input}}", input_text)
        system_prompt = node_data.get("system_prompt", "")
        temperature = float(node_data.get("temperature", 0.7))
        max_tokens = int(node_data.get("max_tokens", 1024))
        full_text = ""
        async for chunk in provider.generate_stream(system_prompt, user_prompt, temperature, max_tokens):
            full_text += chunk
            await emit({"type": "node_output", "node_id": nid, "chunk": chunk})
        return full_text

    # ------------------------------------------------------------------
    # Conditional
    # ------------------------------------------------------------------

    async def _exec_conditional(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        cond_type = node_data.get("condition_type", "contains")
        cond_value = node_data.get("condition_value", "")
        matched = self._check_condition(cond_type, cond_value, input_text)
        out_port = "output_1" if matched else "output_2"
        self.node_outputs[(nid, out_port)] = input_text
        await emit({
            "type": "node_complete", "node_id": nid,
            "output": f"{'Matched' if matched else 'Not matched'} \u2192 {out_port}",
            "duration_ms": 0,
        })
        return input_text

    @staticmethod
    def _check_condition(cond_type: str, cond_value: str, text: str) -> bool:
        if cond_type == "contains":      return cond_value in text
        if cond_type == "not_contains":  return cond_value not in text
        if cond_type == "equals":        return text == cond_value
        if cond_type == "not_equals":    return text != cond_value
        if cond_type == "starts_with":   return text.startswith(cond_value)
        if cond_type == "ends_with":     return text.endswith(cond_value)
        if cond_type == "regex":         return bool(re.search(cond_value, text))
        return False

    # ------------------------------------------------------------------
    # Code
    # ------------------------------------------------------------------

    @staticmethod
    def _exec_code(node_data: dict, input_text: str) -> str:
        code = node_data.get("code", "output = input_data")
        unrestricted = node_data.get("unrestricted", False)
        local_ns: dict[str, Any] = {"input_data": input_text}
        if unrestricted:
            import builtins
            exec(code, {"__builtins__": builtins, "json": json, "os": os, "re": re, "Path": Path}, local_ns)
        else:
            import builtins as _builtins
            safe = {
                "len": len, "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set,
                "range": range, "enumerate": enumerate, "zip": zip,
                "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
                "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                "isinstance": isinstance, "type": type, "print": print,
                "True": True, "False": False, "None": None,
                "json": json, "os": os, "re": re, "Path": Path,
                "open": open, "hasattr": hasattr, "getattr": getattr,
                "__import__": _builtins.__import__,
            }
            exec(code, {"__builtins__": safe}, local_ns)
        return str(local_ns.get("output", ""))

    # ------------------------------------------------------------------
    # Shell
    # ------------------------------------------------------------------

    async def _exec_shell(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        command = node_data.get("command_template", "").replace("{{input}}", input_text)
        if not command.strip():
            raise ValueError("Shell node has no command")
        shell_type = node_data.get("shell_type", "powershell")
        timeout = int(node_data.get("timeout", 30))
        cwd = node_data.get("working_directory", "").strip() or None
        if shell_type == "python":    args = ["python", "-c", command]
        elif shell_type == "bash":    args = ["bash", "-c", command]
        else:                         args = ["powershell", "-NoProfile", "-Command", command]
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE, cwd=cwd,
        )
        try:
            so, se = await asyncio.wait_for(proc.communicate(input=input_text.encode("utf-8")), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise ValueError(f"Shell timed out after {timeout}s")
        stdout = so.decode("utf-8", errors="replace")
        stderr = se.decode("utf-8", errors="replace")
        if stdout:
            await emit({"type": "node_output", "node_id": nid, "chunk": stdout})
        if stderr:
            await emit({"type": "node_output", "node_id": nid, "chunk": f"[stderr] {stderr}"})
        if proc.returncode != 0:
            raise ValueError(f"Shell exited {proc.returncode}: {stderr[:300]}")
        return stdout.strip()

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @staticmethod
    async def _exec_http(node_data: dict, input_text: str) -> str:
        method = node_data.get("method", "GET").upper()
        url = node_data.get("url_template", "").replace("{{input}}", input_text)
        if not url.strip():
            raise ValueError("HTTP node has no URL")
        hdr_raw = node_data.get("headers_json", "").strip()
        headers = json.loads(hdr_raw) if hdr_raw else {}
        body = None
        if method in ("POST", "PUT", "PATCH"):
            bt = node_data.get("body_template", "")
            if bt:
                body = bt.replace("{{input}}", input_text)
        async with httpx.AsyncClient(timeout=float(node_data.get("timeout", 30))) as client:
            resp = await client.request(method, url, headers=headers, content=body)
            resp.raise_for_status()
        extract_path = node_data.get("extract_path", "").strip()
        if extract_path:
            try:
                data = resp.json()
                for key in extract_path.split("."):
                    if key.endswith("]"):
                        base, idx = key[:-1].split("[")
                        data = data[base][int(idx)]
                    else:
                        data = data[key]
                return str(data) if not isinstance(data, str) else data
            except Exception:
                pass
        return resp.text

    # ------------------------------------------------------------------
    # File read / write
    # ------------------------------------------------------------------

    @staticmethod
    def _exec_file_read(node_data: dict, input_text: str) -> str:
        fp = node_data.get("file_path_template", "").replace("{{input}}", input_text).strip()
        if not fp:
            raise ValueError("File Read node has no path")
        p = Path(fp)
        if not p.exists():
            raise ValueError(f"File not found: {fp}")
        return p.read_text(encoding="utf-8")

    @staticmethod
    def _exec_file_write(node_data: dict, input_text: str) -> str:
        fp = node_data.get("file_path", "").strip()
        if not fp:
            raise ValueError("File Write node has no path")
        p = Path(fp)
        p.parent.mkdir(parents=True, exist_ok=True)
        if node_data.get("write_mode") == "append":
            with p.open("a", encoding="utf-8") as f:
                f.write(input_text)
        else:
            p.write_text(input_text, encoding="utf-8")
        return input_text

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    @staticmethod
    def _exec_merge(node_data: dict, inputs: list[str]) -> str:
        if node_data.get("merge_mode") == "json_array":
            return json.dumps(inputs)
        return node_data.get("separator", "\n").join(inputs)

    # ------------------------------------------------------------------
    # ReAct Agent (Think → Act → Observe loop)
    # ------------------------------------------------------------------

    async def _exec_react_agent(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        max_iter = int(node_data.get("max_iterations", 10))
        provider_type = node_data.get("provider", "") or self.settings.get("default_provider", "openai")
        model = node_data.get("model") or self.settings.get("default_model")
        api_key = self._resolve_api_key(provider_type)
        base_url = self.settings.get("ollama_base_url")
        provider = create_provider(provider_type, api_key=api_key, model=model, base_url=base_url)
        temperature = float(node_data.get("temperature", 0.3))
        max_tokens = int(node_data.get("max_tokens", 2048))

        allowed_tools = node_data.get("allowed_tools", ["shell", "code", "http", "file_read", "file_write"])
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",") if t.strip()]

        tool_descriptions = []
        if "shell" in allowed_tools:
            tool_descriptions.append('- shell(command): Execute a shell command and return stdout. Use for running programs, scripts, system commands.')
        if "code" in allowed_tools:
            tool_descriptions.append('- code(python_code): Execute Python code. The last expression or variable "output" is returned.')
        if "http" in allowed_tools:
            tool_descriptions.append('- http(method, url, body?): Make an HTTP request. Returns the response body.')
        if "file_read" in allowed_tools:
            tool_descriptions.append('- file_read(path): Read a file and return its contents.')
        if "file_write" in allowed_tools:
            tool_descriptions.append('- file_write(path, content): Write content to a file.')

        tools_text = "\n".join(tool_descriptions)
        goal = node_data.get("goal", input_text) or input_text
        system_prompt = node_data.get("system_prompt", "") or f"""You are an autonomous agent. You must accomplish the given goal by using available tools.

Available tools:
{tools_text}

To use a tool, respond with exactly one action block:
ACTION: tool_name(arguments)

After receiving the observation, think about what to do next.
When the goal is fully accomplished, respond with:
FINAL_ANSWER: <your final result>

Always think step by step before acting."""

        messages = [{"role": "user", "content": f"Goal: {goal}"}]
        full_log = ""

        for i in range(max_iter):
            if self._cancelled:
                raise ValueError("Agent cancelled")

            await emit({"type": "node_output", "node_id": nid, "chunk": f"\n--- Iteration {i + 1}/{max_iter} ---\n"})

            response = await provider.generate(system_prompt, self._format_messages(messages), temperature, max_tokens)
            await emit({"type": "node_output", "node_id": nid, "chunk": f"THINK: {response}\n"})
            full_log += f"[Think {i+1}] {response}\n"
            messages.append({"role": "assistant", "content": response})

            if "FINAL_ANSWER:" in response:
                answer = response.split("FINAL_ANSWER:", 1)[1].strip()
                await emit({"type": "node_output", "node_id": nid, "chunk": f"\nFINAL ANSWER: {answer}\n"})
                return answer

            action_match = re.search(r'ACTION:\s*(\w+)\((.+?)\)(?:\s|$)', response, re.DOTALL)
            if not action_match:
                messages.append({"role": "user", "content": "Observation: No valid ACTION found in your response. Please use ACTION: tool_name(args) format or FINAL_ANSWER: result."})
                continue

            tool_name = action_match.group(1).strip()
            tool_args = action_match.group(2).strip()

            if tool_name not in allowed_tools:
                observation = f"Error: Tool '{tool_name}' is not available. Available: {', '.join(allowed_tools)}"
            else:
                try:
                    observation = await self._exec_agent_tool(tool_name, tool_args, emit, nid)
                except Exception as exc:
                    observation = f"Error executing {tool_name}: {exc}"

            await emit({"type": "node_output", "node_id": nid, "chunk": f"OBSERVE: {observation[:500]}\n"})
            full_log += f"[Act {i+1}] {tool_name}({tool_args})\n[Observe {i+1}] {observation[:500]}\n"
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        return full_log + "\n[Max iterations reached without FINAL_ANSWER]"

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n\n".join(parts)

    async def _exec_agent_tool(self, tool_name: str, args: str, emit: Emit, nid: str) -> str:
        if tool_name == "shell":
            cmd = args.strip().strip('"').strip("'")
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command", cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            so, se = await asyncio.wait_for(proc.communicate(), timeout=30)
            stdout = so.decode("utf-8", errors="replace").strip()
            stderr = se.decode("utf-8", errors="replace").strip()
            return stdout if proc.returncode == 0 else f"Exit {proc.returncode}: {stderr}"

        if tool_name == "code":
            code = args.strip()
            if code.startswith('"') or code.startswith("'"):
                code = code[1:]
            if code.endswith('"') or code.endswith("'"):
                code = code[:-1]
            import builtins
            local_ns: dict[str, Any] = {"input_data": ""}
            exec(code, {"__builtins__": builtins, "json": json, "os": os, "re": re, "Path": Path}, local_ns)
            return str(local_ns.get("output", ""))

        if tool_name == "http":
            parts = args.split(",", 2)
            method = parts[0].strip().strip('"').strip("'").upper()
            url = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else ""
            body = parts[2].strip().strip('"').strip("'") if len(parts) > 2 else None
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(method, url, content=body)
                return resp.text[:2000]

        if tool_name == "file_read":
            path = args.strip().strip('"').strip("'")
            p = Path(path)
            if not p.exists():
                return f"File not found: {path}"
            return p.read_text(encoding="utf-8")[:5000]

        if tool_name == "file_write":
            parts = args.split(",", 1)
            path = parts[0].strip().strip('"').strip("'")
            content = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else ""
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}"

        return f"Unknown tool: {tool_name}"

    # ------------------------------------------------------------------
    # Conversation Memory
    # ------------------------------------------------------------------

    def _exec_conversation_memory(self, nid: str, node_data: dict, input_text: str) -> str:
        memory_id = node_data.get("memory_id", f"mem_{nid}")
        strategy = node_data.get("strategy", "full")
        if node_data.get("max_messages") is not None:
            max_messages = int(node_data["max_messages"])
        elif node_data.get("max_turns") is not None:
            max_messages = int(node_data["max_turns"]) * 2
        else:
            max_messages = 50
        role = node_data.get("role", "user")

        if memory_id not in self._conversation_stores:
            self._conversation_stores[memory_id] = []
            persist_path = node_data.get("persist_path", "").strip()
            if persist_path:
                p = Path(persist_path)
                if p.exists():
                    try:
                        self._conversation_stores[memory_id] = json.loads(p.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass

        store = self._conversation_stores[memory_id]

        if input_text.strip():
            entry: dict = {"role": role, "content": input_text}
            if node_data.get("record_timestamps", True):
                entry["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            store.append(entry)

        if strategy == "sliding_window" and len(store) > max_messages:
            store[:] = store[-max_messages:]
        elif strategy == "summarize" and len(store) > max_messages:
            store[:] = store[-(max_messages // 2):]

        persist_path = node_data.get("persist_path", "").strip()
        if persist_path:
            p = Path(persist_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(store, indent=2), encoding="utf-8")

        output_format = node_data.get("output_format", "json")
        if output_format == "text":
            return "\n".join(f"{m['role']}: {m['content']}" for m in store)
        return json.dumps(store)

    # ------------------------------------------------------------------
    # Map-Reduce
    # ------------------------------------------------------------------

    async def _exec_map_reduce(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        split_mode = node_data.get("split_mode", "newline")
        reduce_mode = node_data.get("reduce_mode", "concatenate")
        max_parallel = int(node_data.get("max_parallel", 5))
        map_node_type = node_data.get("map_node_type", "code")
        map_node_data = node_data.get("map_node_data", {})

        if split_mode == "json_array":
            try:
                items = json.loads(input_text)
                if not isinstance(items, list):
                    items = [input_text]
            except json.JSONDecodeError:
                items = [input_text]
        elif split_mode == "csv":
            items = [line.strip() for line in input_text.split(",") if line.strip()]
        else:
            items = [line for line in input_text.split("\n") if line.strip()]

        total = len(items)
        results: list[str] = [""] * total
        errors: list[str] = []
        semaphore = asyncio.Semaphore(max_parallel)

        async def process_item(idx: int, item: str) -> None:
            async with semaphore:
                await emit({"type": "node_output", "node_id": nid, "chunk": f"Processing item {idx + 1}/{total}...\n"})
                try:
                    sub_data = dict(map_node_data)
                    output = await self._run_node(f"{nid}_map_{idx}", map_node_type, sub_data, item, [item], emit)
                    results[idx] = output
                except Exception as exc:
                    errors.append(f"Item {idx}: {exc}")
                    results[idx] = ""

        tasks = [asyncio.create_task(process_item(i, item)) for i, item in enumerate(items)]
        await asyncio.gather(*tasks)

        if errors:
            await emit({"type": "node_output", "node_id": nid, "chunk": f"Errors: {'; '.join(errors)}\n"})

        if reduce_mode == "json_array":
            return json.dumps(results)
        elif reduce_mode == "json_merge":
            merged = {}
            for r in results:
                try:
                    merged.update(json.loads(r))
                except (json.JSONDecodeError, TypeError):
                    pass
            return json.dumps(merged)
        elif reduce_mode == "custom_code":
            code = node_data.get("reduce_code", "output = '\\n'.join(items)")
            local_ns: dict[str, Any] = {"items": results}
            safe = {
                "len": len, "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "json": json, "range": range,
                "min": min, "max": max, "sum": sum, "sorted": sorted,
                "enumerate": enumerate, "zip": zip,
                "True": True, "False": False, "None": None,
            }
            exec(code, {"__builtins__": safe}, local_ns)
            return str(local_ns.get("output", ""))
        else:
            separator = node_data.get("separator", "\n")
            return separator.join(results)

    # ------------------------------------------------------------------
    # Embed Node
    # ------------------------------------------------------------------

    async def _exec_embed(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        collection = node_data.get("collection", "default")
        chunk_size = int(node_data.get("chunk_size", 0))
        chunk_overlap = int(node_data.get("chunk_overlap", 50))
        metadata_json = node_data.get("metadata_json", "").strip()
        metadata = json.loads(metadata_json) if metadata_json else {}
        operation = node_data.get("operation", "embed_and_store")

        if chunk_size > 0:
            texts = self._chunk_text(input_text, chunk_size, chunk_overlap)
        else:
            texts = [input_text]

        await emit({"type": "node_output", "node_id": nid, "chunk": f"Embedding {len(texts)} chunk(s)...\n"})
        embeddings = await get_embeddings(texts, self.settings)

        if operation == "embed_only":
            return json.dumps([{"text": t, "embedding_dim": len(e)} for t, e in zip(texts, embeddings)])

        store = VectorStore(collection)
        metas = [{**metadata, "chunk_index": i} for i in range(len(texts))]
        ids = store.insert(texts, embeddings, metas)
        await emit({"type": "node_output", "node_id": nid, "chunk": f"Stored {len(ids)} vectors in '{collection}' (total: {store.count()})\n"})
        return json.dumps({"stored": len(ids), "collection": collection, "total": store.count()})

    @staticmethod
    def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + size])
            chunks.append(chunk)
            i += size - overlap
            if i <= 0:
                i = size
        return chunks if chunks else [text]

    # ------------------------------------------------------------------
    # Vector Store Node
    # ------------------------------------------------------------------

    async def _exec_vector_store(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        collection = node_data.get("collection", "default")
        operation = node_data.get("operation", "query")
        store = VectorStore(collection)

        if operation == "query":
            top_k = int(node_data.get("top_k", 5))
            threshold = float(node_data.get("threshold", 0.0))
            embeddings = await get_embeddings([input_text], self.settings)
            results = store.query(embeddings[0], top_k=top_k, threshold=threshold)
            await emit({"type": "node_output", "node_id": nid, "chunk": f"Found {len(results)} results in '{collection}'\n"})
            return json.dumps(results, indent=2)

        if operation == "insert":
            embeddings = await get_embeddings([input_text], self.settings)
            metadata_json = node_data.get("metadata_json", "").strip()
            metadata = json.loads(metadata_json) if metadata_json else {}
            ids = store.insert([input_text], embeddings, [metadata])
            return json.dumps({"inserted": ids, "total": store.count()})

        if operation == "delete_all":
            count = store.delete(all_docs=True)
            return json.dumps({"deleted": count})

        if operation == "count":
            return json.dumps({"collection": collection, "count": store.count()})

        return json.dumps({"error": f"Unknown operation: {operation}"})

    # ------------------------------------------------------------------
    # RAG Retrieve Node
    # ------------------------------------------------------------------

    async def _exec_rag_retrieve(self, nid: str, node_data: dict, input_text: str, emit: Emit) -> str:
        collection = node_data.get("collection", "default")
        top_k = int(node_data.get("top_k", 5))
        threshold = float(node_data.get("threshold", 0.3))
        output_format = node_data.get("output_format", "context")

        await emit({"type": "node_output", "node_id": nid, "chunk": f"Searching '{collection}' for relevant context...\n"})

        embeddings = await get_embeddings([input_text], self.settings)
        store = VectorStore(collection)
        results = store.query(embeddings[0], top_k=top_k, threshold=threshold)

        if not results:
            await emit({"type": "node_output", "node_id": nid, "chunk": "No relevant results found.\n"})
            return "" if output_format == "context" else "[]"

        score_str = ", ".join(f"{r.get('score', 0):.2f}" for r in results)
        await emit({"type": "node_output", "node_id": nid, "chunk": f"Retrieved {len(results)} relevant chunks (scores: {score_str})\n"})

        if output_format == "json":
            return json.dumps(results, indent=2)

        parts = []
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            text = r.get("text", "")
            parts.append(f"[Relevance: {score:.0%}] {text}")
        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # Graph helpers
    # ------------------------------------------------------------------

    def _topological_sort(self) -> list[str]:
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        all_ids = set(self.nodes.keys())
        for nid, node in self.nodes.items():
            for port in node.get("outputs", {}).values():
                for conn in port.get("connections", []):
                    target = str(conn["node"])
                    graph[nid].append(target)
                    in_degree[target] += 1
        queue: deque[str] = deque(n for n in all_ids if in_degree.get(n, 0) == 0)
        ordered: list[str] = []
        while queue:
            n = queue.popleft()
            ordered.append(n)
            for dep in graph[n]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
        if len(ordered) != len(all_ids):
            raise ValueError("Flow contains a cycle and cannot be executed")
        return ordered

    def _gather_inputs(self, node: dict) -> list[str]:
        inputs: list[str] = []
        for port_name in sorted(node.get("inputs", {}).keys()):
            port = node["inputs"][port_name]
            for conn in port.get("connections", []):
                source_id = str(conn["node"])
                source_port = conn.get("input", "output_1")
                if (source_id, source_port) in self.node_outputs:
                    inputs.append(self.node_outputs[(source_id, source_port)])
        return inputs

    def _resolve_api_key(self, provider_type: str) -> str | None:
        pt = (provider_type or "").lower()
        if pt == "openai":    return self.settings.get("openai_api_key", "")
        if pt == "anthropic": return self.settings.get("anthropic_api_key", "")
        return None
