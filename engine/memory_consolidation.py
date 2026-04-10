"""Promote short-term chat into durable stores (user core, insights, soft notes).

Run after a session, on a schedule, or from POST /api/memory/consolidate.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.embeddings import VectorStore, get_embeddings
from engine.llm_providers import LLMError, create_provider


def _unwrap_assistant_content(content: str) -> str:
    content = (content or "").strip()
    if not content:
        return ""
    try:
        inner = json.loads(content)
        if isinstance(inner, dict) and inner.get("response"):
            return str(inner["response"]).strip()
    except (json.JSONDecodeError, TypeError):
        pass
    return content


def _load_chat(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    return raw


def _transcript_from_messages(messages: list[dict], max_messages: int) -> str:
    lines: list[str] = []
    for msg in messages[-max_messages:]:
        role = str(msg.get("role", "?"))
        content = msg.get("content", "")
        if role == "assistant":
            content = _unwrap_assistant_content(str(content))
        else:
            content = str(content).strip()
        if not content:
            continue
        prefix = "User" if role == "user" else "Atlas" if role == "assistant" else role
        snippet = content[:1200] + ("…" if len(content) > 1200 else "")
        lines.append(f"{prefix}: {snippet}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("No JSON object in model output")
    return json.loads(m.group(0))


def _dedupe_append(existing: list[str], additions: list[str], max_len: int) -> tuple[list[str], int]:
    existing_lower = {x.lower().strip() for x in existing if isinstance(x, str)}
    added = 0
    out = list(existing)
    for item in additions:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s or s.lower() in existing_lower:
            continue
        out.append(s[:400])
        existing_lower.add(s.lower())
        added += 1
        if len(out) > max_len:
            out = out[-max_len:]
    return out, added


async def consolidate_short_term_to_long_term(
    settings: dict,
    *,
    chat_path: str | Path = "assistant/chat_history.json",
    memory_layers_path: str | Path = "assistant/memory_layers.json",
    persona_path: str | Path = "assistant/persona.json",
    log_path: str | Path = "assistant/consolidation_log.jsonl",
    max_transcript_messages: int = 48,
    embed_insights: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Read short-term chat; ask LLM what to promote; merge into long-term stores."""
    chat_p = Path(chat_path)
    mem_p = Path(memory_layers_path)
    persona_p = Path(persona_path)
    log_p = Path(log_path)

    messages = _load_chat(chat_p)
    transcript = _transcript_from_messages(messages, max_transcript_messages)
    report: dict[str, Any] = {
        "ok": True,
        "skipped": False,
        "transcript_chars": len(transcript),
        "dry_run": dry_run,
        "merged": {},
    }

    if len(transcript.strip()) < 80:
        report["skipped"] = True
        report["reason"] = "transcript_too_short"
        return report

    if not mem_p.exists():
        report["ok"] = False
        report["error"] = f"Missing {mem_p}"
        return report

    memory = json.loads(mem_p.read_text(encoding="utf-8"))
    uc = memory.setdefault("user_core", {})
    uc.setdefault("stable_facts", [])
    uc.setdefault("boundaries", [])
    existing_snapshot = {
        "preferred_name": uc.get("preferred_name", ""),
        "pronouns": uc.get("pronouns", ""),
        "stable_facts": uc.get("stable_facts", [])[-24:],
        "boundaries": uc.get("boundaries", [])[-12:],
        "working_summary": memory.get("working_summary", ""),
    }

    provider_type = (settings.get("default_provider") or "openai").lower()
    model = settings.get("default_model") or None
    api_key = None
    if provider_type == "openai":
        api_key = settings.get("openai_api_key") or None
    elif provider_type == "anthropic":
        api_key = settings.get("anthropic_api_key") or None
    base_url = settings.get("ollama_base_url")

    try:
        provider = create_provider(
            provider_type,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
    except LLMError as e:
        report["ok"] = False
        report["error"] = str(e)
        return report

    system = """You consolidate chat into durable memory. Output ONLY a single JSON object, no markdown fences.

Rules:
- stable_facts: at most 5 NEW lines ONLY if the USER (not the assistant) clearly stated a lasting fact in the transcript. Never promote assistant guesses, filler, or inferred biography into stable_facts. Do NOT repeat anything in existing_durable.
- boundaries: at most 3 NEW lines (things to avoid, naming, topics off-limits) only if the USER stated them.
- preferred_name / pronouns: set only if the USER clearly states them; otherwise use empty string "".
- working_summary: one sentence capturing current focus; empty string if unclear.
- insights: at most 3 short lines about observable patterns — never assert specific counts (kids, pets) the user did not state.
- relationship_note: one soft note or null. Never claim concrete unpublished biographical details.

If nothing new is worth saving, return empty arrays and null relationship_note."""

    user_payload = (
        "EXISTING_DURABLE_JSON:\n"
        + json.dumps(existing_snapshot, indent=2)
        + "\n\nCHAT_TRANSCRIPT:\n"
        + transcript
        + '\n\nReturn JSON with keys: preferred_name, pronouns, stable_facts, boundaries, working_summary, insights, relationship_note'
    )

    try:
        raw = await provider.generate(system, user_payload, temperature=0.15, max_tokens=900)
        proposed = _extract_json_object(raw)
    except Exception as e:
        report["ok"] = False
        report["error"] = f"consolidation_llm_failed: {e}"
        return report

    pref = str(proposed.get("preferred_name") or "").strip()
    pro = str(proposed.get("pronouns") or "").strip()
    facts = proposed.get("stable_facts") or []
    bounds = proposed.get("boundaries") or []
    wsum = str(proposed.get("working_summary") or "").strip()
    insights = proposed.get("insights") or []
    rel_note = proposed.get("relationship_note")

    if not isinstance(facts, list):
        facts = []
    if not isinstance(bounds, list):
        bounds = []
    if not isinstance(insights, list):
        insights = []

    merged_facts, n_facts = _dedupe_append(uc.get("stable_facts", []), facts, max_len=40)
    merged_bounds, n_bounds = _dedupe_append(uc.get("boundaries", []), bounds, max_len=20)

    changes: dict[str, Any] = {
        "stable_facts_added": n_facts,
        "boundaries_added": n_bounds,
        "insights_embedded": 0,
        "relationship_note_appended": False,
    }

    if pref and not dry_run:
        uc["preferred_name"] = pref[:120]
        changes["preferred_name_set"] = True
    if pro and not dry_run:
        uc["pronouns"] = pro[:40]
        changes["pronouns_set"] = True

    if not dry_run:
        uc["stable_facts"] = merged_facts
        uc["boundaries"] = merged_bounds
        if wsum:
            memory["working_summary"] = wsum[:500]

    report["merged"] = changes

    if dry_run:
        report["proposal"] = proposed
        return report

    mem_p.parent.mkdir(parents=True, exist_ok=True)
    with mem_p.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

    if isinstance(rel_note, str) and rel_note.strip() and persona_p.exists():
        note = rel_note.strip()[:400]
        try:
            persona = json.loads(persona_p.read_text(encoding="utf-8"))
            notes = persona.get("relationship_notes", [])
            if note not in notes and note.lower() not in {n.lower() for n in notes if isinstance(n, str)}:
                notes.append(note)
                if len(notes) > 20:
                    notes = notes[-20:]
                persona["relationship_notes"] = notes
                persona_p.write_text(json.dumps(persona, indent=2), encoding="utf-8")
                changes["relationship_note_appended"] = True
        except (json.JSONDecodeError, OSError):
            pass

    if embed_insights and insights:
        texts = [str(i).strip() for i in insights[:3] if str(i).strip()]
        if texts:
            try:
                embeddings = await get_embeddings(texts, settings)
                store = VectorStore("atlas_insights")
                metas = [{"source": "consolidation"} for _ in texts]
                store.insert(texts, embeddings, metas)
                changes["insights_embedded"] = len(texts)
            except Exception:
                changes["insights_embedded_error"] = True

    log_p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report": {k: report[k] for k in ("ok", "skipped", "merged") if k in report},
        "proposal_keys": list(proposed.keys()) if isinstance(proposed, dict) else [],
    }
    with log_p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return report


async def _cli() -> None:
    root = Path(__file__).resolve().parent.parent
    import os

    os.chdir(root)
    settings_path = root / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    report = await consolidate_short_term_to_long_term(
        settings,
        dry_run="--dry-run" in sys.argv,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(_cli())
