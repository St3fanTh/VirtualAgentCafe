"""Explicit public messages emitted by an agent's CLI helper; private text stays private."""

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ROLES = {"ada": "backend", "turing": "frontend"}


class PeerMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID
    task_id: UUID
    recipient: Literal["ada", "turing"]
    text: str = Field(min_length=1, max_length=256)
    reply: bool = False


HELPER = """#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from uuid import uuid4
parser = argparse.ArgumentParser(description="Send an explicitly public cafe message")
parser.add_argument("recipient", choices=["ada", "turing"])
parser.add_argument("text")
parser.add_argument("--reply", action="store_true")
args = parser.parse_args()
if args.recipient == SENDER or not args.text.strip() or len(args.text) > 256:
    parser.error("Choose the other agent and provide 1-256 public characters")
root = Path(__file__).resolve().parent
outbox = root / "outbox.jsonl"
if not outbox.resolve().is_relative_to(root) or (outbox.exists() and outbox.stat().st_size > 65536):
    parser.error("Outbox unavailable or full")
message = {"message_id": str(uuid4()), "task_id": TASK_ID, "recipient": args.recipient,
           "text": args.text.strip(), "reply": REPLY_TASK or args.reply}
with outbox.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(message, ensure_ascii=False) + "\\n")
print("Public message queued")
"""


def safe_cafe_path(root: Path, agent_id: str, filename: str) -> Path:
    workspace = root / agent_id
    path = workspace / ".cafe" / filename
    if not workspace.resolve().is_relative_to(root) or not path.resolve().is_relative_to(workspace):
        raise ValueError("Invalid message workspace")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def prepare_helper(root: Path, agent_id: str, task_id: UUID, reply: bool) -> int:
    helper = safe_cafe_path(root, agent_id, "send_message.py")
    constants = f"SENDER = {agent_id!r}\nTASK_ID = {str(task_id)!r}\nREPLY_TASK = {reply!r}\n"
    helper.write_text(constants + HELPER, encoding="utf-8")
    outbox = safe_cafe_path(root, agent_id, "outbox.jsonl")
    if outbox.exists() and outbox.stat().st_size > 32768:
        outbox.write_text("", encoding="utf-8")
    return outbox.stat().st_size if outbox.exists() else 0


def read_outbox(root: Path, agent_id: str, offset: int) -> tuple[int, list[dict]]:
    path = safe_cafe_path(root, agent_id, "outbox.jsonl")
    if not path.exists():
        return offset, []
    messages = []
    with path.open("rb") as stream:
        stream.seek(offset)
        for _ in range(8):
            line = stream.readline(4097)
            if not line or not line.endswith(b"\n"):
                break
            offset = stream.tell()
            if len(line) > 4096:
                continue
            try:
                messages.append(json.loads(line))
            except (ValueError, UnicodeDecodeError):
                continue
    return offset, messages


def deliver_inbox(root: Path, recipient: str, sender: str, text: str, correlation: UUID):
    path = safe_cafe_path(root, recipient, "inbox.jsonl")
    existing = (
        path.read_text(encoding="utf-8").splitlines()[-31:]
        if path.exists() and path.stat().st_size <= 65536
        else []
    )
    existing.append(
        json.dumps(
            {
                "sender": sender,
                "role": ROLES[sender],
                "text": text,
                "correlation_id": str(correlation),
            },
            ensure_ascii=False,
        )
    )
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")
