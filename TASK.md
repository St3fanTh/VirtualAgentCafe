# VirtualAgentCafe — Entwicklungsauftrag an Codex

> **Rolle:** Du bist leitender Softwareentwickler für ein ereignisgesteuertes 2D-Spiel, das reale Aktivitäten mehrerer KI-Agenten darstellt. Lies zuerst `AGENTS.md` und `SKILLS.md` (falls vorhanden). Implementiere inkrementell; behaupte niemals, Tests ausgeführt zu haben, die du nicht ausgeführt hast.

## Kontext
- Repository auf WSL-Host: `/mnt/f/Workspace/VirtualAgentCafe`
- Repository im Dev Container: `/workspace`
- Git-Remote: `git@github.com:St3fanTh/VirtualAgentCafe.git` (SSH-Zugang muss vorher vom Nutzer eingerichtet werden)
- Godot-Editor kann auf Windows laufen; Godot CLI läuft headless im Container.
- Ziel: Beobachter-Spielwelt, **keine** Simulation angeblich auslesbarer interner LLM-Gedanken.

## Zielbild / MVP
Eine kleine, lauffähige Pixel-Art-Caféwelt mit zwei Agenten-Avataren. Wenn ein Agent nachweislich einen Modellaufruf startet, Dateien bearbeitet, Tests ausführt, eine Nachricht sendet, wartet oder fertig wird, aktualisiert die Welt dessen Position, Animation, Status und ggf. Sprechblase. Zuerst mit einem deterministischen Demo-Simulator, danach über einen Adapter für echte Agenten-Events.

## Technologiewahl
- **Python 3.12+** für FastAPI, Pydantic, asynchrone WebSockets, Event-Bus, Simulator und Adapter.
- **Godot 4.x / GDScript** für Tilemap, Figuren, Animationen, Wegfindung, HUD und WebSocket-Client.
- **pytest + pytest-asyncio + httpx** für Unit-, API-, Integrations- und Smoke-Tests.
- **Godot Headless CLI** für Projektimport und Laufzeittests; zusätzliche GDScript-Tests mit kleinem Test-Runner oder einem gepflegten Test-Framework nur, wenn es zuverlässig installierbar ist.
- **Ruff** für Python-Formatierung und Linting; **GitHub Actions** für CI.
- Kein Unity, React, TypeScript, MCP oder externer LLM-Zugang im MVP erforderlich.

## Gewünschte Struktur (vorhandene Struktur respektieren)
```text
VirtualAgentCafe/
├── AGENTS.md
├── TASK.md
├── SKILLS.md
├── README.md
├── compose.yaml
├── Dockerfile
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── virtual_agent_cafe/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── bus.py
│   │   ├── simulator.py
│   │   └── adapters/
│   └── tests/
├── game/
│   ├── project.godot
│   ├── scenes/
│   ├── scripts/
│   ├── assets/
│   └── tests/
├── scripts/
│   ├── check.sh
│   └── demo.sh
├── docs/
│   ├── architecture.md
│   └── event-schema.md
└── .github/workflows/ci.yml
```

## Anforderungen
1. Backend-Endpunkte `GET /health`, `GET /agents` und `WS /ws/events`; optionale Event-Ingestion nur lokal und mit Validierung.
2. Typisierte Events mit `event_id`, `agent_id`, `type`, `timestamp`, `sequence`, `correlation_id`, `payload`. Eventtypen: `agent.started`, `agent.thinking`, `agent.coding`, `agent.testing`, `agent.message`, `agent.waiting`, `agent.error`, `agent.finished`.
3. Demo-Simulator mit zwei Agenten, reproduzierbaren Ereignissen und einstellbarer Geschwindigkeit; läuft ohne API-Key.
4. Godot-Welt mit zwei Figuren, Arbeitsplätzen, Teststation, Gesprächsecke, Statusanzeige und Sprechblasen.
5. Event-zu-Animation-Mapping; Figuren dürfen auf der visuellen Ebene nachlaufen, aber Backend-Events niemals blockieren.
6. WebSocket-Reconnect mit Backoff, Queue-Limit, Zustands-Snapshot beim Neuverbinden und sichtbarem Offline-Indikator.
7. Kein Logging von Secrets, privaten Prompts oder kompletten Tool-Ausgaben als Standard. Eingaben validieren und Größen begrenzen.
8. Ausführbare README-Anleitung für WSL + Compose + Godot unter Windows; dokumentierte Portfreigabe nur auf `127.0.0.1`.
9. Optionaler echter Codex-Adapter **erst nach** stabilem MVP: ausschließlich öffentlich verfügbare/erfasste Laufzeitereignisse; keine erfundenen Gedanken.

## Meilensteine und Abnahmekriterien
### M0 — Bestandsaufnahme
- `pwd`, `git status`, `git remote -v`, Branch, Toolversionen prüfen.
- Vorhandene Dateien lesen, Änderungen planen, nichts blind überschreiben.
- Prüfen, ob Git-Push möglich ist, **ohne** einen Test-Push zu erzwingen.

### M1 — Backend und Tests
- Eventmodelle, Bus, API und Simulator implementieren.
- Tests: Eventvalidierung, Zustandsübergänge, Reihenfolge, Queue-Limit, `/health`, `/agents`, WebSocket-Empfang und ungültige Payloads.

### M2 — Godot-Welt
- Hauptszene, zwei Agenten, HUD, Animationen, Netzwerk-Client.
- Tests: Godot-Import, Headless-Start, Event→Zustand; im Editor sichtbare Demo.

### M3 — Integration und CI
- `scripts/demo.sh` startet Backend und Simulator nachvollziehbar.
- `scripts/check.sh` führt Ruff, pytest und Godot-Headless-Checks aus und liefert bei Fehlern einen Exit-Code ungleich 0.
- E2E-Smoke-Test: Simulator → WebSocket → erwartete Events.
- GitHub Actions führt dieselben Checks nach Push/PR aus.

### M4 — Echte Agentenaktivitäten
- Adapter-Schnittstelle implementieren, dann Codex-Ereignisse anbinden, soweit durch die gewählte Laufzeit tatsächlich verfügbar.
- Nachricht zwischen Agenten erzeugt Sprechblase und Gesprächsanimation; „thinking“ heißt nur laufender Modellaufruf.

### M5 — Polishing
- Pixel-Art verbessern, Animationswechsel glätten, Fehlerzustände visualisieren, Performance testen.

## Git-Regeln
- Auf `feat/agent-cafe-mvp` arbeiten; nicht direkt auf `main`.
- Vor jedem Commit: `git status`, `git diff --check`, relevante Tests; niemals Secrets stagen.
- Kleine Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
- **Nach jedem vollständig getesteten Meilenstein pushen**, sofern die Nutzerfreigabe für Pushes vorliegt und SSH-Authentifizierung funktioniert. Keine Force-Pushes, kein automatischer Merge, kein Überschreiben fremder Änderungen.
- Keine Änderung an SSH-Schlüsseln, Git-Credentials, Remote-URL oder Branch-Schutzregeln ohne Rückfrage.
- Falls Git-Push scheitert: Fehler melden, nicht Schutzmechanismen umgehen.
- `AGENTS.md` oder diese Datei ist **kein Scheduler**: Für zeitgesteuerte Läufe ist eine separate Orchestrierung erforderlich.

## Fertig, wenn
- Ein frischer Checkout lässt sich mit dokumentierten Befehlen installieren und testen.
- Der Demo-Modus zeigt zwei Figuren, Zustandswechsel und mindestens eine Nachricht.
- Backend- und Godot-Checks sind grün, CI läuft, README ist aktuell.
- Ein Meilensteinbericht nennt geänderte Dateien, Testkommandos + Ergebnisse, Commit-Hash, Push-Status und offene Punkte.

## Erste Anweisung
**Beginne mit M0.** Zeige eine kurze Implementierungsplanung und arbeite anschließend M1 ab. Überspringe keine Tests und erfinde keine Testergebnisse.
