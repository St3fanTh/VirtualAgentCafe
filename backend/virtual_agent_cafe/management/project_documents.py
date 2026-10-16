"""Bounded project Markdown, editable only by the authenticated controller user."""

import hashlib
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .config import Identifier, StrictModel
from .files import ApprovedFiles

DocumentName = Literal["AGENTS.md", "PLANNING.md"]
NAMES = {"AGENTS.md": ("AGENTS.md", "agents.md"), "PLANNING.md": ("PLANNING.md", "planning.md")}


class ProjectDocumentInput(StrictModel):
    project: Identifier
    name: DocumentName
    content: str = Field(min_length=1, max_length=12000)
    expected_sha256: str = Field(pattern=r"^([a-f0-9]{64})?$")


def load_documents(root: Path) -> dict:
    files = ApprovedFiles(root)
    result = {}
    for canonical, aliases in NAMES.items():
        paths = [files.path(name) for name in aliases]
        present = [path for path in paths if path.exists()]
        if len(present) > 1:
            # On case-insensitive filesystems aliases can refer to the same file.
            if not present[0].samefile(present[1]):
                raise ValueError(f"Keep only one spelling of {canonical}")
            present = present[:1]
        path = present[0] if present else paths[0]
        content = ""
        if present:
            if not path.is_file() or path.stat().st_size > 12000:
                raise ValueError(f"{canonical} must be a Markdown file of at most 12 KiB")
            content = path.read_text(encoding="utf-8")
        result[canonical] = {
            "file": path.name,
            "content": content,
            "exists": bool(present),
            "sha256": hashlib.sha256(content.encode()).hexdigest() if present else "",
        }
    return result


def save_document(root: Path, data: ProjectDocumentInput) -> dict:
    if len(data.content.encode()) > 12000 or not data.content.lstrip("\ufeff \t\r\n").startswith(
        "#"
    ):
        raise ValueError("Project Markdown needs a heading and at most 12 KiB")
    current = load_documents(root)[data.name]
    if current["sha256"] != data.expected_sha256:
        raise ValueError("Project document changed on disk. Reload before saving your changes.")
    files = ApprovedFiles(root)
    path = files.path(current["file"])
    temporary = files.path(f".cafe-document-{uuid4()}.tmp")
    try:
        temporary.write_text(data.content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return load_documents(root)
