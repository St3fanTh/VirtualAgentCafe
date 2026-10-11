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

## M2 — Godot-Café und Live-Verbindung
- Vorheriger Meilenstein: 6c74e56, Push erfolgreich.
- Implementiert: prozedurale Pixel-Art-Tilemap, zwei Figuren, Arbeitsplätze,
  Teststation, Gesprächsecke, Café und Wartelounge; ereignisabhängige Bewegung und
  Animationen für alle acht Zustände, Sprechblasen, Status/HUD, Offline-Anzeige.
- Anklicken öffnet Aufgabendialog; echte Aufgabe wird erst im Codex-Modus freigeschaltet.
- WebSocket mit Backoff (0.5–15 s), begrenzten Paketen, Snapshot-Verarbeitung,
  Duplikatunterdrückung und Resync bei Sequenzlücken.
- Geändert: game/project.godot, game/scenes/cafe.tscn, game/scripts/*.gd,
  game/tests/test_states.gd, game/tests/test_live.gd, backend/main.py.
- Tests: pytest 19 bestanden; Ruff grün; Godot Import, 120-Frame-Headless-Start und
  Zustandstests erfolgreich; echter Uvicorn→WebSocket→Godot-Livetest erfolgreich,
  inklusive Figuren-Auswahl und Empfang von Coding/Testing/Message/Finished.
- Bei wiederholtem Backendtest Cancellation-Race gefunden und behoben:
  WebSocket räumt Subscriber auch bei Abbruch durch ASGI-Server zuverlässig auf.
- Offene Punkte: Kein grafischer Displayserver hier; visuelle Editorprüfung noch offen.
  Docker nicht vorhanden. Codex-Aufgaben-Endpunkt folgt nach Integrations-/CI-Meilenstein.
- Commit-ID: `git log --format='%h %s' --grep='implement Godot cafe and event animations'`.
- Nächste Schritte: reproduzierbare Check-/Demo-Skripte, CI, Setup-Dokumentation.

## M3 — Reproduzierbare Integration und CI
- Vorheriger Meilenstein: 33b37f4, Push erfolgreich.
- Implementiert: scripts/check.sh, scripts/demo.sh, eigenständiger Prozess-Livetest
  mit temporärem Port, Python-Abhängigkeitslock mit Hashes, GitHub Actions,
  Container-Healthcheck, sicherer Compose-Start und optionales SSH-Agent-Forwarding.
- Geändert: scripts/*, .github/workflows/ci.yml, backend/requirements.lock,
  Dockerfile, compose.yaml, compose.ssh.yaml, ruff.toml, README.md, docs/codex-adapter.md.
- Docker installiert Backend beim Image-Build, ohne Schreibzugriff auf Hostquellen
  beim Start zu benötigen. Runtime-Volume hält isolierte Aufgabenbereiche schreibbar.
- Tests: scripts/check.sh komplett grün: Ruff, 19 pytest-Tests, Godot-Import,
  Zustandstests, Headless-Start, Uvicorn→WebSocket→Godot inkl. Figuren-Auswahl.
- Compose-Konfiguration mit eigenständiger Docker Compose CLI validiert.
- Offene Punkte: kein Docker-Daemon vorhanden, Build/Container-Smoke hier nicht
  ausführbar; CI enthält diese Prüfungen, Status noch nicht verifiziert.
  Visuelle Editorprüfung und Live-Codex-Ausführung folgen separat.
- Commit-ID: `git log --format='%h %s' --grep='add reproducible integration checks and CI'`.
- Nächste Schritte: Codex-Adapter, Aufgaben- und Kommunikations-API, echte Ausführung.

## M3-Korrektur — Ausführungsrechte im Git-Index
- M3-Commit: 0805673, Push erfolgreich; erster CI-Lauf fehlgeschlagen (Exit 126).
- Ursache: Mount speichert chmod nicht als Git-Dateimodus; Skripte waren im Index 100644.
- Behoben: git update-index --chmod=+x für check.sh, demo.sh und entrypoint.sh.
- Tests: komplette scripts/check.sh-Kette erneut grün (19 pytest, Ruff, Godot,
  eigenständiger Live-WebSocket-Test). CI wird mit diesem Push neu gestartet.
- Geänderte Dateien: drei Skripte (nur Dateimodus), PROGRESS.md.
- Commit-ID: `git log --format='%h %s' --grep='preserve executable script permissions'`.
- Parallel gestarteter echter Codex-Probelauf: CLI authentifiziert, Turn gestartet,
  aber alle Shelltools mit bwrap-Namespace-Fehler abgewiesen; keine Dateien erzeugt.
  Keine Sandbox-Umgehung vorgenommen. M4 implementiert sichtbaren Fehlerzustand.

## M4 — Codex-Anbindung implementiert, Live-Abnahme umgebungsbedingt offen
- Vorherige Korrektur: d061319, Push erfolgreich. GitHub Actions für d061319
  vollständig erfolgreich, inklusive Docker-Build und Container-Healthcheck:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38177618970
- Implementiert: Adapter-Interface, Codex JSONL-Observer und echter CLI-Subprozess,
  Prompts über stdin, isolierte persistente Agenten-Git-Arbeitsbereiche,
  Aufgaben-/Status-/Abbruch-API, begrenzte Historie, Timeouts und Prozessgruppen-Cleanup,
  explizite Peer-Nachrichten mit bestätigter Zustellung und gemeinsamer Korrelation.
- Godot kann Aufgaben senden, Abbrechen und Nachrichten zustellen; zeigt Ergebnisordner
  und sichere Statusdetails. CLI im Image auf geprüfte 0.162.1 festgelegt.
- Rohtexte, Reasoning, Befehle, Prompts und Tool-Ausgaben werden nicht veröffentlicht.
  Thinking bedeutet belegten aktiven Modellturn; CLI liefert keinen API-Aufruf-Trace.
  Coding nur bei file_change; Testing nur bei geparsten Testbefehlen.
- Geändert: adapters/*, jobs.py, main.py, models.py, Backendtests/Fixture,
  game/scripts/cafe.gd, game/tests/test_tasks.gd, scripts/codex_smoke.py,
  Dockerfile, README.md, docs/codex-adapter.md.
- Reguläre Tests: scripts/check.sh grün; 50 pytest-Tests, Ruff, Godot-Import,
  Zustandsmapping, Headless-Start, Demo→Godot. Zusätzlich Godot-UI→HTTP→CLI-Fixture→
  Events→Godot für Aufgaben, Bearbeiten/Testen/Fertig, Peer-Nachricht und Abbruch grün.
- ECHTER Live-Test tatsächlich ausgeführt: authentifizierter Codex-Turn und öffentliche
  Events beobachtet; Shell und File-Change durch fehlende Linux-Namespaces blockiert.
  Ergebnis korrekt agent.error, KEIN agent.finished. Keine Sandbox-Umgehung.
  `scripts/codex_smoke.py` deshalb derzeit fehlgeschlagen; Live-Abnahme NICHT bestanden.
- Nutzer nach sandboxfähigem Container gefragt. Alle übrigen Prüfungen reproduzierbar;
  CI nutzt explizit eine CLI-Subprozess-Fixture, keine vermeintlichen Live-Läufe.
- Commit-ID: `git log --format='%h %s' --grep='integrate Codex tasks and observed runtime events'`.
- Offene Probleme: sandboxfähige Laufzeit für echte Dateiänderungen/Tests, grafische
  Sichtprüfung. Nächster unabhängiger Schritt: Animationswechsel sichtbar glätten,
  Queue-/Reconnect-Last prüfen; Live-Test nach Umgebungsänderung wiederholen.
