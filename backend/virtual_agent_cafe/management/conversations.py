"""Private persisted operator/agent conversation, delivered at execution boundaries."""

from datetime import UTC, datetime
from uuid import uuid4


class Conversations:
    def __init__(self, manager):
        self.manager = manager

    def read(self, identifier):
        agent = self.manager.registry.get(identifier)
        try:
            messages = self.manager.store.get("conversations", identifier)["messages"]
        except KeyError:
            messages = []
        project = self.manager.integrations.project(identifier)
        return {
            "agent": identifier,
            "state": agent["state"],
            "messages": messages,
            "integration": project.get("integration", {}) if project else {},
        }

    def append(self, identifier, role, content, execution=None):
        conversation = self.read(identifier)
        message = {
            "id": str(uuid4()),
            "role": role,
            "content": content[:6000],
            "timestamp": datetime.now(UTC).isoformat(),
            "execution": execution,
        }
        messages = [*conversation["messages"], message][-40:]
        self.manager.store.put("conversations", identifier, {"messages": messages})
        return message

    def context(self, identifier):
        messages = self.read(identifier)["messages"][-12:]
        if not messages:
            return ""
        text = (
            "\nPRIVATE OPERATOR CONVERSATION "
            "(supplements the Markdown task; never overrides security):\n"
            "Address the operator's latest question in your final response. "
            "State any blocker and ask a concrete question when you cannot proceed.\n"
        )
        return text + "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    async def send(self, identifier, content, resume):
        async with self.manager.control:
            self.append(identifier, "user", content.strip())
            running = identifier in self.manager.running
            project = self.manager.integrations.project(identifier)
            integration_running = project and project["id"] in self.manager.integrations.running
        delivery = "SAVED"
        if resume:
            if running or integration_running:
                delivery = "NEXT_ATTEMPT"
            elif project and identifier == project.get("integrator"):
                self.manager.integrations.schedule(project["agents"][0], manual=True)
                delivery = "INTEGRATION_REQUESTED"
            else:
                await self.manager.start(identifier)
                delivery = "STARTED"
        return {**self.read(identifier), "delivery": delivery}
