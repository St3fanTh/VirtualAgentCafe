# VirtualAgentCafe — Benötigte Skills und Arbeitsregeln

Dieses Dokument beschreibt die **Fähigkeiten**, die ein Codex-Entwicklungsagent für das Projekt benötigt. Es ist eine Kompetenz- und Tool-Checkliste, **kein automatisch installierbares Codex-Skill-Paket**. Ein konkretes Codex-Skill lässt sich bei Bedarf später als eigener `SKILL.md`-Ordner anlegen.

## Pflicht-Skills

| Skill | Technologie / Tool | Was der Agent können muss | Nachweis |
|---|---|---|---|
| Repository-Arbeit | Git, SSH, GitHub | Status prüfen, Feature-Branch, Commits, Push, Konflikte erkennen | `git status`, `git remote -v`, `git ls-remote origin HEAD` |
| Python-Backend | Python 3.12+, FastAPI, Pydantic | Typisierte Event-API und asynchronen WebSocket-Server entwickeln | `pytest` |
| Nebenläufigkeit | `asyncio` | Nicht blockierender Event-Bus, begrenzte Queues, Reconnect und Backpressure | Unit- und Integrationstests |
| Game Development | Godot 4, GDScript | Szenen, Nodes, Tilemap, Character-Animation, HUD, Navigation | Godot-Headless-Import + Smoke-Test |
| Event-Protokolle | JSON, WebSockets | Versionierbares Event-Schema, Sequenzen, Korrelation, Fehlerfälle | Schema- und E2E-Tests |
| Testautomatisierung | pytest, pytest-asyncio, httpx, Godot CLI | Reproduzierbare Unit-, API-, Integrations- und Smoke-Tests | `scripts/check.sh` |
| Container | Docker/Podman Compose, Linux | Bind-Mounts, Benutzerrechte, Ports, Build und Start | `compose config`, Container-Smoke-Test |
| CI/CD | GitHub Actions | Checks auf Push und Pull Request ausführen | Erfolgreicher CI-Workflow |
| Dokumentation | Markdown | README, Architektur, Setup und Fehlerbehebung | Start mit README allein möglich |
| Sicherheit | SSH-Agent, Secret-Hygiene | Keine Keys ins Image/Repo; nur minimale Rechte | `.gitignore` und Secret-Review |

## Nice-to-have-Skills
- **Pixel-Art / 2D-Animation:** Spritesheets, einfache Platzhalter, Animationszustände und Übergänge.
- **Pathfinding:** Godot `NavigationAgent2D`, sofern für die Karte erforderlich.
- **Observability:** strukturierte Logs, Event-Korrelation, Debug-HUD.
- **Codex-Integration:** verfügbare Ereignis- und Tool-Schnittstellen der tatsächlich eingesetzten Codex-Laufzeit prüfen, Adapter schreiben.
- **MCP:** erst erwägen, wenn Editor-Automation per Dateien und Godot CLI nicht mehr ausreicht. MCP ist für das MVP **nicht nötig**.

## Container-Werkzeuge
Der Dev Container sollte mindestens bereitstellen:

```bash
python3 --version
node --version
npm --version
codex --version
godot --version
git --version
ssh -V
```

Für den Python-Teil zusätzlich `pytest`, `pytest-asyncio`, `httpx`, `fastapi`, `uvicorn`, `websockets`, `pydantic` und `ruff`. Verwende ein virtuelles Environment oder eine sauber deklarierte `pyproject.toml`-Installation.

## Git-Zugriff aus WSL / Dev Container

1. WSL-Repository: `/mnt/f/Workspace/VirtualAgentCafe` → im Container `/workspace` mounten.
2. SSH-Agent in WSL starten und **vorhandenen** Schlüssel laden:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
ssh-add -l
```

3. **Öffentlichen** Schlüssel `~/.ssh/id_ed25519.pub` als schreibberechtigten Deploy Key für das Repository hinterlegen. Den privaten Schlüssel niemals hochladen.
4. SSH-Remote verwenden: `git@github.com:St3fanTh/VirtualAgentCafe.git`.
5. WSL-Verbindung prüfen: `ssh -T git@github.com` und `git ls-remote origin HEAD`.
6. Für den Container **SSH-Agent-Forwarding** konfigurieren; keine privaten Schlüssel mounten. Der genaue Socket-Mount hängt davon ab, ob Docker Desktop mit WSL-Integration oder ein nativer Docker-/Podman-Daemon läuft. Socket-Zugriff und `known_hosts` im Container explizit testen.
7. Die Agent-Identität sollte nur die minimal notwendigen Rechte besitzen. Push ausschließlich auf einen Feature-Branch.

**Achtung:** Zugriff auf den SSH-Agent-Socket ermöglicht Authentifizierung mit geladenen Schlüsseln. Bei einem automatisierten Agenten daher einen eigenen, nur für dieses Repository gültigen Deploy Key bevorzugen.

## Teststrategie (Pflicht)

### Unit-Tests
- Eventmodell akzeptiert gültige und verwirft ungültige Payloads.
- Agenten-Zustandsautomat bildet Eventtypen korrekt ab.
- Sequenznummern und Duplikate werden kontrolliert behandelt.
- Queue-Limits verhindern unbeschränktes Speicherwachstum.

### API-/WebSocket-Tests
- `/health` liefert erfolgreichen Status.
- `/agents` liefert aktuellen Agentenstatus.
- WebSocket überträgt Events in erwarteter Reihenfolge.
- Verbindungstrennung und Reconnect werden behandelt.
- Unzulässige Eventgrößen werden abgelehnt.

### Godot-Tests
```bash
godot --headless --path game --editor --quit
godot --headless --path game --quit-after 120
```

- Zusätzlich Zustandsmapping automatisiert testen.
- Visuelle Prüfung im Windows-Godot-Editor: zwei Figuren, Bewegung, Animation, Sprechblase, Offline-Status.

### End-to-End-Test
- Demo-Simulator startet zwei Agenten.
- Backend verteilt Events.
- Test-WebSocket-Client empfängt mindestens `agent.coding`, `agent.testing`, `agent.message` und `agent.finished`.
- Keine echten LLM-API-Schlüssel notwendig.

## Regeln für autonomes Arbeiten
1. Vor Änderung Projektstruktur und bestehende Dateien prüfen.
2. Pro Meilenstein kleine Änderungen und Tests durchführen.
3. Nach grünem Testlauf committen; mit vorheriger Freigabe auf Feature-Branch pushen.
4. Keine Git-Force-Pushes, keine automatischen Merges und keine Änderungen an Credentials.
5. Fehlgeschlagene Tests nicht verbergen; Fehler beheben oder dokumentieren.
6. Nach jedem Meilenstein Statusbericht mit Testresultaten, Commit und Push-Status erstellen.
7. Bei fehlender Grafik/Editor-Integration mit reproduzierbaren Headless-Checks arbeiten; visuelle Qualität nicht ohne Sichtprüfung behaupten.

## Empfohlene Lern- und Implementierungsreihenfolge
**Git/SSH und Container → Python-Eventmodell → FastAPI/WebSockets → pytest → Godot/GDScript → Godot Headless → Integration → CI → echter Codex-Adapter → optional MCP.**
