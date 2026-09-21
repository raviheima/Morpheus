"""
AI summary of analysis findings for non-technical readers (judges, panels).

Uses the OpenAI-compatible chat completions API.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def is_configured() -> bool:
    return bool(os.environ.get("MORPHEUS_AI_API_KEY", "").strip())


def _build_prompt(
    presentation: Dict[str, Any], case_meta: Optional[Dict[str, Any]] = None
) -> str:
    case_meta = case_meta or {}
    cs = presentation.get("case_summary") or {}
    docs = (presentation.get("documents_of_interest") or [])[:15]
    suspicious = (
        presentation.get("suspicious_files")
        or presentation.get("suspicious")
        or []
    )[:15]
    emails = (presentation.get("sample_emails") or presentation.get("emails") or [])[:10]
    deleted = (presentation.get("deleted_files") or [])[:10]
    images = (presentation.get("images") or [])[:8]

    payload = {
        "case_number": case_meta.get("case_number"),
        "case_name": case_meta.get("case_name"),
        "summary_counts": cs,
        "documents_of_interest": docs,
        "suspicious_files": suspicious,
        "sample_emails": emails,
        "deleted_files": deleted,
        "images": images,
    }

    return (
        "You are a digital forensics assistant. Write a clear case summary for a judge "
        "or non-technical reader. Use simple English (about B1 level). "
        "Do not invent facts. Only use the JSON findings below.\n\n"
        "Structure your answer with these headings:\n"
        "1. What this case is about\n"
        "2. What was examined\n"
        "3. Important findings (bullet list)\n"
        "4. Items that need human review\n"
        "5. Limits (what this tool did not prove)\n\n"
        "Keep the whole answer under 600 words. Be calm and precise.\n\n"
        f"FINDINGS JSON:\n{json.dumps(payload, default=str)[:12000]}"
    )


def generate_summary(
    presentation: Dict[str, Any],
    case_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = os.environ.get("MORPHEUS_AI_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "AI is not configured. Set MORPHEUS_AI_API_KEY in the environment.",
            "summary": None,
        }

    base = os.environ.get(
        "MORPHEUS_AI_BASE_URL", "https://api.openai.com/v1"
    ).rstrip("/")
    model = os.environ.get("MORPHEUS_AI_MODEL", "gpt-4o-mini")
    url = f"{base}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You write careful forensic summaries for courts. Never invent evidence.",
            },
            {"role": "user", "content": _build_prompt(presentation, case_meta)},
        ],
    }

    for attempt in range(3):
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return {
                    "ok": False,
                    "error": "Empty response from AI provider",
                    "summary": None,
                }
            return {"ok": True, "error": None, "summary": text, "model": model}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2**attempt)
                continue
            if exc.code in (429, 500, 502, 503, 504):
                detail = (
                    "The AI provider is temporarily busy or rate-limited. "
                    "Please try again shortly."
                )
            return {
                "ok": False,
                "error": f"AI HTTP {exc.code}: {detail}",
                "summary": None,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "summary": None}
