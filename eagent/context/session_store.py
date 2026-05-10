"""Session persistence in JSONL format."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eagent.paths import env_root
from eagent.core.types import (
    ImageBlock,
    ImageSource,
    Message,
    RedactedThinkingBlock,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

SESSIONS_BASE = env_root() / "sessions"
TRANSCRIPT_FILE = "transcript.jsonl"
META_FILE = "meta.json"


@dataclass(frozen=True)
class SessionSummary:
    id: str
    cwd: str
    message_count: int
    updated_at: int

    @property
    def prefix(self) -> str:
        return self.id[:8]


def get_session_dir(session_id: str) -> Path:
    return SESSIONS_BASE / session_id


def get_session_path(session_id: str) -> Path:
    return get_session_dir(session_id) / TRANSCRIPT_FILE


def _now_ms() -> int:
    return int(time.time() * 1000)


def _serialize_message(message: Message) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for block in message.content:
        payload = dict(vars(block))
        if isinstance(block, ImageBlock):
            payload["source"] = dict(vars(block.source))
        blocks.append(payload)
    return {"role": message.role, "content": blocks, "id": message.id}


def _deserialize_message(raw: dict[str, Any]) -> Message:
    content = []
    for block in raw.get("content", []):
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            content.append(TextBlock(type="text", text=str(block.get("text", ""))))
        elif btype == "tool_use":
            content.append(
                ToolUseBlock(
                    type="tool_use",
                    id=str(block.get("id", "")),
                    name=str(block.get("name", "")),
                    input=block.get("input", {}) if isinstance(block.get("input"), dict) else {},
                )
            )
        elif btype == "tool_result":
            content.append(
                ToolResultBlock(
                    type="tool_result",
                    tool_use_id=str(block.get("tool_use_id", "")),
                    content=block.get("content", ""),
                    is_error=bool(block.get("is_error", False)),
                )
            )
        elif btype == "thinking":
            content.append(ThinkingBlock(type="thinking", thinking=str(block.get("thinking", ""))))
        elif btype == "redacted_thinking":
            content.append(
                RedactedThinkingBlock(type="redacted_thinking", data=str(block.get("data", "")))
            )
        elif btype == "image":
            source = block.get("source", {})
            media_type = (
                source.get("media_type", "image/png") if isinstance(source, dict) else "image/png"
            )
            data = source.get("data", "") if isinstance(source, dict) else ""
            content.append(
                ImageBlock(
                    type="image",
                    source=ImageSource(type="base64", media_type=str(media_type), data=str(data)),
                )
            )
    role = raw.get("role", "user")
    return Message(
        role=role if role in {"user", "assistant"} else "user", content=content, id=raw.get("id")
    )


def _write_meta(
    session_id: str, cwd: str, message_count: int, created_at: int | None = None
) -> None:
    folder = get_session_dir(session_id)
    folder.mkdir(parents=True, exist_ok=True)
    now = _now_ms()
    meta = {
        "id": session_id,
        "createdAt": created_at if created_at is not None else now,
        "updatedAt": now,
        "cwd": cwd,
        "messageCount": message_count,
    }
    (folder / META_FILE).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


async def init_session(session_id: str, cwd: str) -> None:
    _write_meta(session_id, cwd=cwd, message_count=0)


async def save_message(session_id: str, message: Message, cwd: str | None = None) -> None:
    folder = get_session_dir(session_id)
    folder.mkdir(parents=True, exist_ok=True)

    entry = {
        "type": message.role,
        "message": _serialize_message(message),
        "timestamp": _now_ms(),
        "id": str(uuid.uuid4()),
    }
    with get_session_path(session_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    existing = None
    meta_path = folder / META_FILE
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            existing = None

    message_count = 1
    if existing and isinstance(existing.get("messageCount"), int):
        message_count = int(existing["messageCount"]) + 1

    _write_meta(
        session_id,
        cwd=cwd or (existing.get("cwd") if isinstance(existing, dict) else ""),
        message_count=message_count,
        created_at=existing.get("createdAt") if isinstance(existing, dict) else None,
    )


async def load_session(session_id: str) -> list[Message]:
    path = get_session_path(session_id)
    if not path.exists():
        return []

    messages: list[Message] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            raw_message = entry.get("message")
            if isinstance(raw_message, dict):
                messages.append(_deserialize_message(raw_message))
        except Exception:
            continue
    return messages


def list_sessions_sync() -> list[dict[str, Any]]:
    SESSIONS_BASE.mkdir(parents=True, exist_ok=True)
    sessions: list[dict[str, Any]] = []

    for folder in SESSIONS_BASE.iterdir():
        if not folder.is_dir():
            continue
        meta_path = folder / META_FILE
        if meta_path.exists():
            try:
                sessions.append(json.loads(meta_path.read_text(encoding="utf-8")))
                continue
            except Exception:
                pass

        transcript = folder / TRANSCRIPT_FILE
        mtime = int(transcript.stat().st_mtime * 1000) if transcript.exists() else 0
        count = 0
        if transcript.exists():
            count = sum(1 for _ in transcript.open("r", encoding="utf-8"))

        sessions.append(
            {
                "id": folder.name,
                "createdAt": mtime,
                "updatedAt": mtime,
                "cwd": "",
                "messageCount": count,
            }
        )

    sessions.sort(key=lambda x: x.get("updatedAt", 0), reverse=True)
    return sessions


async def list_sessions() -> list[dict[str, Any]]:
    return list_sessions_sync()


def list_session_summaries_sync(limit: int | None = None) -> list[SessionSummary]:
    summaries: list[SessionSummary] = []
    for session in list_sessions_sync():
        session_id = str(session.get("id") or "")
        if not session_id:
            continue
        count = session.get("messageCount")
        updated = session.get("updatedAt")
        summaries.append(
            SessionSummary(
                id=session_id,
                cwd=str(session.get("cwd") or ""),
                message_count=int(count) if isinstance(count, int) else 0,
                updated_at=int(updated) if isinstance(updated, int) else 0,
            )
        )
        if limit is not None and len(summaries) >= limit:
            break
    return summaries


async def list_session_summaries(limit: int | None = None) -> list[SessionSummary]:
    return list_session_summaries_sync(limit)
