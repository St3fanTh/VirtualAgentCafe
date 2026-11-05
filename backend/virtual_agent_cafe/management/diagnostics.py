"""Private execution diagnostics; never collect credentials or reasoning events."""

import json
import os
import re
from datetime import UTC, datetime


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if re.search(
                r"(?i)(password|secret|token|api[_-]?key|authorization|private[_-]?key)", k
            )
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    for key, secret in os.environ.items():
        if len(secret) >= 8 and re.search(r"(?i)(token|secret|password|api_?key)", key):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(
        r"-----BEGIN [^-\n]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-\n]*PRIVATE KEY-----|$)",
        "[REDACTED PRIVATE KEY]",
        value,
    )
    value = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", value)
    value = re.sub(
        r"""(?i)((?:[\w-]*(?:token|password|secret|api[_-]?key)[\w-]*)["']?\s*[:=]\s*)("[^"\n]*"|'[^'\n]*'|[^\s,;]+)""",
        r"\1[REDACTED]",
        value,
    )
    value = re.sub(
        r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{16,})\b", "[REDACTED]", value
    )
    return re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", value)


def export(store, execution):
    # One locked read transaction: running executions export a coherent snapshot.
    with store.lock:
        store.db.execute("BEGIN")
        try:
            row = store.db.execute(
                "SELECT data FROM records WHERE kind='executions' AND id=?", (execution,)
            ).fetchone()
            if row is None:
                raise KeyError(execution)
            run = json.loads(row[0])
            evidence = {}
            for kind in ("runtime_test_outputs", "validation_outputs"):
                rows = store.db.execute(
                    "SELECT id,data FROM records WHERE kind=? AND (id=? OR substr(id,1,?)=?)",
                    (kind, execution, len(execution) + 1, execution + ":"),
                ).fetchall()
                evidence[kind] = {key: json.loads(data) for key, data in rows}
            logs = [
                {"sequence": seq, **json.loads(data)}
                for seq, data in store.db.execute(
                    "SELECT sequence,data FROM logs WHERE execution=? ORDER BY sequence",
                    (execution,),
                )
            ]
            events = [
                {"sequence": seq, **json.loads(data)}
                for seq, data in store.db.execute(
                    "SELECT sequence,data FROM runtime_events WHERE execution=? ORDER BY sequence",
                    (execution,),
                )
            ]
        finally:
            store.db.rollback()
    return redact(
        {
            "format": "virtual-agent-cafe-diagnostics-v1",
            "exported_at": datetime.now(UTC).isoformat(),
            "execution": run,
            "activity": logs,
            "runtime_events": events,
            **evidence,
            "capture": {
                "runtime_event_count": len(events),
                "notes": "Snapshot of persisted evidence. Earlier runs may lack runtime events. "
                "Provider truncation and the runtime stream limit still apply. Reasoning and "
                "credential files are not collected. Known secret patterns are redacted; "
                "review project content before sharing.",
            },
        }
    )
