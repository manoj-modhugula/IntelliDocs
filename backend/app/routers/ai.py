"""Conversation title generation via the configured LLM."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_auth, UserResponse
from app.services.llm import aux_llm_service

router = APIRouter()
logger = logging.getLogger(__name__)


class MessagesReq(BaseModel):
    # Frontend sends messages with `{ role, content, ... }`
    messages: list[dict[str, Any]]


def _conversation_text(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = str(m.get("role", "user"))
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role.title()}: {content}")
    return "\n".join(lines).strip()


def _extract_json_obj(text: str) -> dict[str, Any]:
    """
    Best-effort extraction of a JSON object from LLM output.
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    # Try to extract substring between first '{' and last '}'.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(text[start : end + 1])


def _safe_str(x: Any, limit: Optional[int] = None) -> str:
    s = str(x or "").strip()
    if limit is not None:
        s = s[:limit]
    return s


@router.post("/generate-title")
async def generate_title(
    req: MessagesReq,
    _user: UserResponse = Depends(require_auth),
) -> dict[str, str]:
    try:
        conversation = _conversation_text(req.messages)
        if not conversation:
            return {"title": ""}

        prompt = (
            "You are generating a short descriptive conversation title for a chat UI.\n"
            "Return ONLY JSON.\n\n"
            "JSON format:\n"
            '{ "title": "..." }\n\n'
            "Rules:\n"
            "- Title must be max 60 characters.\n"
            "- Avoid prefixes like \"Chat\", \"Conversation\", \"New Chat\".\n"
            "- Use the user's intent (what they asked for), not the raw text.\n\n"
            f"Conversation:\n{conversation}"
        )

        # Bedrock output is plain text; we parse JSON ourselves.
        text = await aux_llm_service.generate(prompt, max_tokens=80, temperature=0.5)
        obj = _extract_json_obj(text)
        return {"title": _safe_str(obj.get("title"), limit=60)}
    except Exception as e:
        logger.warning("generate_title failed: %s", e)
        return {"title": ""}

