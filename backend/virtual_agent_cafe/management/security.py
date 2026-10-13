import os
import secrets
from pathlib import Path

from fastapi import HTTPException, Request


class ManagementAccess:
    """Native user capability; never mounted into managed execution environments."""

    def __init__(self, root: Path):
        token = os.getenv("VAC_MANAGEMENT_TOKEN")
        path = root / "control-token"
        if token is None:
            if path.is_symlink():
                raise ValueError("Control token must not be a symlink")
            if not path.exists():
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(secrets.token_urlsafe(32))
            path.chmod(0o600)
            token = path.read_text().strip()
        if len(token) < 24:
            raise ValueError("Management token needs at least 24 characters")
        self.token = token

    def require(self, request: Request):
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, "Bearer " + self.token):
            raise HTTPException(401, "Management authorization required")
