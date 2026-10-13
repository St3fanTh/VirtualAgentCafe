import hashlib
import os
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from .config import Identifier, MarkdownRef
from .storage import Store


class ApprovedFiles:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        path = self.root / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Path is outside the approved root")
        # Reject all symlink components, including symlinks that currently point inside.
        current = self.root
        for part in Path(relative).parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlinks are not approved")
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Path is outside the approved root")
        return path


class MarkdownManager:
    def __init__(self, root: Path, kind: str, store: Store):
        self.files = ApprovedFiles(root)
        self.kind = kind
        self.store = store

    def load(self, name: str) -> dict:
        TypeAdapter(MarkdownRef).validate_python(name)
        path = self.files.path(name)
        if path.stat().st_size > 16000:
            raise ValueError("Markdown exceeds 16 KiB")
        content = path.read_text(encoding="utf-8")
        if not content.strip() or not content.lstrip().startswith("#"):
            raise ValueError("Markdown needs a heading and instructions")
        return {
            "file": name,
            "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }

    def save(self, name: str, content: str) -> dict:
        TypeAdapter(MarkdownRef).validate_python(name)
        if len(content.encode()) > 16000 or not content.strip().startswith("#"):
            raise ValueError("Markdown needs a heading and at most 16 KiB")
        target = self.files.path(name)
        temporary = self.files.path(f".{uuid4()}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        record = self.load(name)
        self.store.put(self.kind, name, {"file": name, "sha256": record["sha256"]})
        return record

    def list(self) -> list[dict]:
        # Files, rather than cached database text, are always authoritative.
        return [self.load(p.name) for p in sorted(self.files.root.glob("*.md"))]


class WorkspaceManager:
    def __init__(self, root: Path, store: Store):
        self.files = ApprovedFiles(root)
        self.store = store

    def create(self, identifier: str) -> dict:
        TypeAdapter(Identifier).validate_python(identifier)
        path = self.files.path(identifier)
        path.mkdir(exist_ok=True)
        record = {"id": identifier, "path": str(path)}
        self.store.put("workspaces", identifier, record)
        return record

    def get(self, identifier: str) -> Path:
        TypeAdapter(Identifier).validate_python(identifier)
        self.store.get("workspaces", identifier)
        path = self.files.path(identifier)
        if not path.is_dir():
            raise ValueError("Workspace is unavailable")
        return path
