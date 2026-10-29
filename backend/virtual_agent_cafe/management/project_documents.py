"""Bounded project Markdown, editable only by the authenticated controller user."""

import hashlib
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .config import Identifier, StrictModel
from .files import ApprovedFiles

MAX_DOCUMENT_BYTES = 64 * 1024

DocumentName = Literal["AGENTS.md", "PLANNING.md"]
NAMES = {"AGENTS.md": ("AGENTS.md", "agents.md"), "PLANNING.md": ("PLANNING.md", "planning.md")}


class ProjectDocumentInput(StrictModel):
    project: Identifier
    name: DocumentName
    # Parsing ceiling allows a precise storage-limit error for oversized submissions.
    content: str = Field(min_length=1, max_length=MAX_DOCUMENT_BYTES * 2)
    expected_sha256: str = Field(pattern=r"^([a-f0-9]{64})?$")


def validate_document_content(name: str, content: str) -> None:
    size = len(content.encode("utf-8"))
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError(
            f"{name} is too large: {size} UTF-8 bytes; maximum {MAX_DOCUMENT_BYTES} "
            "(64 KiB). Archive completed requirements or shorten the document."
        )
    if not content.strip("\ufeff \t\r\n"):
        raise ValueError(f"{name} is empty. Enter project instructions; a heading is optional.")


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
            if not path.is_file():
                raise ValueError(f"{canonical} must be a regular Markdown file, not a directory")
            size = path.stat().st_size
            if size > MAX_DOCUMENT_BYTES:
                raise ValueError(
                    f"{canonical} is too large: {size} UTF-8 bytes; maximum "
                    f"{MAX_DOCUMENT_BYTES} (64 KiB). Shorten the file in your project folder."
                )
            content = path.read_text(encoding="utf-8")
        result[canonical] = {
            "file": path.name,
            "content": content,
            "exists": bool(present),
            "sha256": hashlib.sha256(content.encode()).hexdigest() if present else "",
        }
    return result


def save_document(root: Path, data: ProjectDocumentInput) -> dict:
    validate_document_content(data.name, data.content)
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
