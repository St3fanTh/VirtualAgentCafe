"""Private, read-only release notes from persisted execution recaps, never chat logs."""

import re

# Preserve explicit requirement IDs; never infer implementation from a task assignment.
HEADING = re.compile(
    r"^#{1,4}\s+(?:Requirement\s+)?"
    r"(?P<id>\d+(?:\.\d+)+|REQ[-_][A-Za-z0-9_.-]+)"
    r"(?:\s*[:—–-]\s*|\s+)?(?P<title>[^\n]*)$",
    re.MULTILINE | re.IGNORECASE,
)


def sections(recap: str) -> list[dict]:
    matches = list(HEADING.finditer(recap))
    if not matches:
        return [{"requirement": "", "title": "General recap", "description": recap.strip()}]
    result = []
    if recap[: matches[0].start()].strip():
        result.append(
            {
                "requirement": "",
                "title": "Summary",
                "description": recap[: matches[0].start()].strip(),
            }
        )
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(recap)
        result.append(
            {
                "requirement": match["id"],
                "title": match["title"].strip(),
                "description": recap[match.end() : end].strip(),
            }
        )
    return result


def overview(store) -> dict:
    agents = {
        row["config"]["id"]: {
            "id": row["config"]["id"],
            "name": row["config"]["name"],
            "entries": [],
        }
        for row in store.list("agents")
    }
    runs = sorted(store.list("executions"), key=lambda r: r.get("started_at", ""), reverse=True)
    for run in runs:
        if not run.get("changelog"):
            continue
        identifier = run["agent_id"]
        group = agents.setdefault(
            identifier, {"id": identifier, "name": run.get("agent_name", identifier), "entries": []}
        )
        group["entries"].append(
            {
                "execution": run["id"],
                "date": run.get("started_at", ""),
                "task": run.get("task", ""),
                "workspace": run.get("workspace_path", ""),
                "branch": run.get("branch", ""),
                "commit": run.get("agent_commit"),
                "status": run.get("status", ""),
                "publication": run.get("publication", "NOT_REQUESTED"),
                "published": run.get("published", {}),
                "workflow": run.get("workflow", {}),
                "acceptance": run.get("acceptance", "UNVERIFIED"),
                "sections": sections(run["changelog"]),
            }
        )
    return {"agents": sorted(agents.values(), key=lambda a: (a["name"].lower(), a["id"]))}
