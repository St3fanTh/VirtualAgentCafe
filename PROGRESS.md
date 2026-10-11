# VirtualAgentCafe — Fortschritt

## M0 — Bestandsaufnahme und sichere Grundlage
- SSH-Authentifizierung und Remote-Zugriff erfolgreich; leerer Test-Commit
  `12b356acabd9dc1451240487de1eb7ccc75c5a60` erfolgreich gepusht.
- Nutzer hat main zum Default gemacht und Test-Branch entfernt; bestätigt mit ls-remote.
- Entwicklungsbranch feat/virtual-agent-cafe-mvp angelegt; vorhandene Dateien erhalten.
- Anforderungen vollständig gelesen, zusätzlich unter TASK.md / SKILLS.md verfügbar.
- AGENTS.md erstellt. Private Schlüssel bleiben lokal und werden durch .gitignore
  und .dockerignore ausgeschlossen; Dockerfile kopiert keine Schlüssel mehr.
- Containerbasis auf Debian Trixie für Python >=3.12 umgestellt; Ruff ergänzt.
- Geändert: AGENTS.md, TASK.md, SKILLS.md, Dockerfile, compose.yaml,
  docker/entrypoint.sh, .gitignore, .dockerignore, ursprüngliche Anforderungsdateien.
- Prüfungen: Git/SSH/Remote/Push erfolgreich; Godot 4.4.1 und Codex 0.162.1 vorhanden.
  Python im laufenden Container ist 3.11; separate Python-3.12-Umgebung wird installiert.
  Noch kein Anwendungscode, daher Unit-/Integrations-/Godot-Projektchecks nicht anwendbar.
- Docker-Daemon/CLI fehlt hier; Container-Build muss außerhalb validiert werden.
- Commit-ID: `git log --format='%h %s' --grep='initialize secure project foundation'`.
  Eigene Commit-ID kann nicht in demselben Commit enthalten sein; Folgebericht trägt Hash nach.
- Nächste Schritte: M1 Eventmodell, begrenzter Bus, REST/WebSocket und Simulator mit Tests.

## M1 — Backend, Ereignisse und Demo
- Vorheriger Meilenstein: c42aac3, Push erfolgreich.
- Implementiert: validierte unveränderliche Events, acht Zustände, zwei Agenten,
  globale Sequenzen, Duplikatschutz, begrenzter Fan-out, Snapshot bei Overflow/Connect,
  /health, /agents, /ws/events und deterministischer Simulator mit konfigurierbarem Takt.
- Geändert: backend/pyproject.toml, backend/virtual_agent_cafe/{models,bus,main,simulator}.py,
  Paketinitialisierung, backend/tests/test_backend.py, docs/architecture.md, docs/event-schema.md.
- Tests: Python 3.12.15; Ruff check/format grün; pytest: 19 bestanden, einschließlich
  API/WebSocket-Reconnect und Simulator→WebSocket-Integration.
- Testproblem behoben: Testzugriff auf Bus muss im Server-Eventloop erfolgen (portal.call).
- Godot-Projektcheck noch nicht anwendbar, Projekt folgt in M2. Godot CLI verfügbar.
- Offene Punkte: TestClient meldet eine vorgelagerte httpx-Deprecation;
  Container-Build hier mangels Docker nicht ausführbar.
- Commit-ID: `git log --format='%h %s' --grep='implement typed agent event backend'`.
- Nächste Schritte: Caféwelt, Netzwerkclient, Zustandstests, Interaktion für Aufgaben.
