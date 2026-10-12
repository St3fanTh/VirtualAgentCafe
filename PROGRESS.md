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

## M5 — Darstellung, Last und Wiederanlauf; Live-Code-Abnahme weiterhin offen
- M4-Commit f30069f gepusht; GitHub Actions vollständig grün inkl. Container-Build:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38177963295
- Implementiert: begrenzte visuelle Ereignisqueue (16 Zustände/Figur) mit 0.65 s
  Mindestanzeige; kurze tatsächliche Coding-/Testing-Ereignisse bleiben sichtbar.
  Backend und HUD laufen unabhängig weiter; Snapshot ersetzt visuelle Queue sofort.
- Echte Codex-Antwort wird privat unter .cafe/last-response.md gespeichert,
  Ergebnisdateipfad im HUD; keine Rohantwort im öffentlichen Ereignisstream.
- Echter Textauftrag durch CodexAdapter/JobManager erfolgreich ausgeführt und
  gespeicherte Antwort unabhängig geprüft: PASS. Das bestätigt reale Modellanbindung,
  ersetzt NICHT die weiterhin blockierte Live-Abnahme für Dateiänderungen/Testtools.
- Tests: scripts/check.sh vollständig grün, 52 pytest-Tests; Lasttest mit 5000 Events
  und vier begrenzten Subscriberqueues; echter Backend-Neustart bei laufendem Godot
  prüft Offline-Anzeige, Backoff und erneuten Snapshot. Godot-Zustandstests prüfen
  nun Mindestanzeige, Queue-Limit und Resync. Aufgaben-/Kommunikations-/Abbruch-E2E grün.
- Auf expliziten Nutzerwunsch: separate compose.privileged.yaml mit privileged:true
  für codex/backend, Standardkonfiguration unverändert. Keine Änderung laufender
  Container oder Host-Sicherheit vorgenommen; Docker-Daemon ist hier nicht vorhanden.
  Non-root node und Codex workspace-write bleiben bestehen.
- Compose inklusive Privileged-Override validiert. Neubau/Smoke-Anleitung unter
  docs/container-sandbox.md dokumentiert; broad host access ist explizites lokales Opt-in.
- Geändert: character.gd, cafe.gd, test_states.gd, test_reconnect.gd,
  backend/tests/{test_backend,test_reconnect}.py, adapters/codex.py, jobs.py,
  README.md, docs/{architecture,codex-adapter,container-sandbox}.md, compose.privileged.yaml.
- Offene Abnahme: Privileged-Container muss auf dem Nutzerhost neu erstellt werden;
  anschließend unshare und scripts/codex_smoke.py ausführen. Keine erfolgreichen
  Live-Dateiänderungen/Tests behauptet. Grafische Sichtprüfung in Windows-Godot offen.
- Commit-ID: `git log --format='%h %s' --grep='polish event presentation and container sandbox setup'`.
- Nächste Schritte: CI dieses Commits bestätigen; nach Nutzer-Neubau echte Code-/Test-
  Abnahme wiederholen und Ergebnis in PROGRESS.md festhalten.

## M4-Live-Korrektur — Hilfsbefehle als Warnungen behandeln
- Vorheriger Commit: fe19dd3; dessen GitHub Actions vollständig erfolgreich.
- Nutzer hat Privileged-Container neu gebaut. Sein echter Lauf zeigt nun Datei-
  änderungen und gestartete/abgeschlossene Tests; ursprüngliche Namespaceblockade
  dort behoben. Vollständige Live-Abnahme noch nicht bestätigt.
- Fehler im Adapter: Jeder gescheiterte Hilfsbefehl wurde dauerhaft als Gesamtfehler
  gespeichert, auch nach erfolgreicher Bearbeitung und erfolgreichen Tests.
  Ein Suchbefehl kann in einem leeren Workspace regulär mit Exit 1 enden.
- Behoben: Hilfsfehler weiterhin agent.error und Warnungszähler; abgeschlossenem
  Turn wird bei ausschließlich solchen Fehlern Finished mit Warnungssummary erlaubt.
  Failing Tests, failed File-Change, Runtime-Fehler und Sandboxfehler bleiben blockierend.
  Sandbox-Erkennung um bwrap-Fehler erweitert, neue Turns benötigen eigenen Abschluss.
  Fehlerdetail unterscheidet nun Sandbox, Tests, File-Change und Runtime.
- Geändert: backend/virtual_agent_cafe/adapters/codex.py,
  backend/tests/test_codex.py, docs/codex-adapter.md, PROGRESS.md.
- Tests: scripts/check.sh vollständig grün; 59 pytest-Tests; 7 neue Regressionen
  decken Nutzerfolge mit Hilfsfehler→Edit→grünen Tests, Warnungssummary und verbleibende
  echte Fehler ab. Godot Import/Zustände/Headless/Livetest grün; Aufgaben-E2E und
  Backend-Neustart-Godot-Reconnect ebenfalls grün.
- SSH und Remote vor Push erneut erfolgreich geprüft. Keine Credentials geändert.
- Eigene Agentenumgebung unverändert nicht privileged; daher tatsächlicher Code-
  Smoke nach Korrektur hier nicht erfolgreich ausführbar. Nutzer kann ohne erneuten
  Image-Build mit aktueller Quelle testen:
  `PYTHONPATH=/workspace/backend python3 scripts/codex_smoke.py`.
- Commit-ID: `git log --format='%h %s' --grep='allow completed Codex turns after helper command warnings'`.
- Nächster Schritt: Nutzer lädt Commit und wiederholt echten Smoke im funktionierenden
  Privileged-Container; privates Prompt/Tool-Logging weiterhin ausgeschaltet.

## Live-Abnahme — Echte Codex-Dateiänderungen und Tests erfolgreich
- Ausgangscommit 28a1be9; Branch feat/virtual-agent-cafe-mvp sauber übernommen.
- Nach Nutzer-Neustart: unshare -Ur true erfolgreich; SSH-Agent mit Repository-Key,
  GitHub-Authentifizierung und git ls-remote erfolgreich. Keine Credentialänderung.
- Tatsächlich ausgeführt: `PYTHONPATH=/workspace/backend /opt/venv/bin/python
  scripts/codex_smoke.py` gegen angemeldete Codex CLI 0.162.1.
- Ergebnis: agent.started → thinking → message → waiting → vorübergehender
  Hilfsfehler → coding → coding → testing → waiting → message → finished.
  `Real Codex smoke: PASS`; generierte greeting.py/test_greeting.py vorhanden und
  generierte unittest unabhängig erneut erfolgreich ausgeführt. Live-Code-Abnahme
  somit bestanden. Kein CLI-Sandbox-Bypass; workspace-write bleibt aktiviert.
- Umgebungsfehler behoben: Codex-Shell wählte Systempython ohne Pydantic statt
  installierter /opt/venv. scripts/environment.sh wählt nutzbare lokale .venv bzw.
  Container-venv und aktuelle Repositoryquelle; check.sh/demo.sh nutzen ihn.
  scripts/codex-smoke.sh bietet denselben stabilen Einstieg für echte Smoke-Läufe.
- Geändert: scripts/environment.sh, scripts/codex-smoke.sh, scripts/check.sh,
  scripts/demo.sh, README.md, docs/codex-adapter.md, docs/container-sandbox.md.
- Tests: scripts/check.sh in neuer Umgebung Python 3.13.5 vollständig grün:
  Ruff, 59 pytest-Tests, Godot 4.4.1 Import, Zustandsmapping, Headless-Lauf,
  Demo→WebSocket→Godot, Aufgaben-/Nachrichten-/Abbruch-E2E und Backend-Reconnect.
- Offene Punkte: Sichtprüfung in Windows-Godot (Nutzer möchte jetzt Probelauf),
  CI dieses Abschlusscommits noch zu bestätigen. Keine visuellen Befunde erfunden.
- Commit-ID: `git log --format='%h %s' --grep='validate live Codex execution and select project environment'`.
- Nächste Schritte: Demo auf Nutzerhost mit docker compose starten, game/project.godot
  in Windows öffnen/F5; danach Codex-Modus und erste echte Aufgabe über Figur starten.

## Grafik-Meilenstein — Höhere Auflösung und atmosphärische Shader
- Nutzerauftrag: Café höher auflösen und mit Shadern optisch verbessern.
- Referenzcanvas 1920×1280, Startfenster 1440×960; ursprüngliches Seitenverhältnis
  erhalten. Größere native Schrift für HUD, Stationsnamen, Figuren und Sprechblasen;
  Aufgabendialog mit angepassten Abständen, Kontrast, Fokus-/Hover-Stilen.
- Vier neue Compatibility-CanvasItem-Shader: versetzte Holzplanken/Maserung,
  Fensterglas mit Skyline/Reflexion/Regen, Monitorleuchten/Scanlines und warme
  Lichtflächen/Fensterstrahl/Vignette. Atmosphäre über Button deaktivierbar.
- Monitorfarben folgen tatsächlichen Backendzuständen; Agentenanimationen und
  Ereignisfluss bleiben unverändert. Shaderflächen ignorieren Mauseingaben.
- Möbel erweitert: Kontaktschatten, Kantenlichter, Tastaturdetails, Polster,
  Teppiche, Pendelleuchten und Regale. GUI getrennt von Raumbeleuchtung.
- Geändert: game/project.godot, game/scripts/{world,cafe,character}.gd,
  game/shaders/*.gdshader, game/tests/render_preview.gd, .github/workflows/ci.yml,
  README.md, docs/graphics.md, docs/images/cafe-preview.png und dieser Bericht.
- Bereits vorhandene Nutzeränderungen (Godot-Formatierung/Featurefeld und Szenen-UID)
  erhalten; game/scenes/cafe.tscn nicht als Teil dieses Meilensteins gestagt.
- Tests: scripts/check.sh vollständig grün: Ruff, 59 pytest-Tests inkl. Aufgaben-
  /Nachrichten-/Abbruch-E2E und Reconnect, Godot-Import, Zustandsmapping, Headless,
  Live-Demo→WebSocket→Godot.
- Zusätzlich echtes OpenGL-Rendering mit Godot 4.4.1 Compatibility/Mesa llvmpipe
  unter temporärem Xvfb; 1920×1280 Vorschauen mit/ohne Effekte und Dialog erstellt
  und visuell geprüft. Keine Shader-/Scriptfehler. Anfangs fehlende Display-Libraries
  temporär unter /tmp bereitgestellt; System und Docker-Sicherheitsprofil unverändert.
  Dummy-Audio vermeidet fehlendes Audiogerät; virtuelle VSync-Warnung bleibt harmlos.
- Im Screenshot grobe Bodenstruktur und überlappende/deskalierte Beschriftungen
  erkannt und verbessert; gerenderte Demo-Vorschau in docs/images abgelegt.
- CI erhält zusätzlichen echten Shader-Render mit Screenshot-Artefakten; dessen
  Remote-Ergebnis nach Push noch zu prüfen. Windows-GPU separat nicht gemessen.
- Commit-ID: `git log --format='%h %s' --grep='enhance cafe resolution and atmospheric shaders'`.
- Nächste Schritte: Nutzer pullt Featurebranch, startet Godot neu/F5 und vergleicht
  mit dem Atmosphere-Schalter; Backend-Neubau für reine Grafikänderung nicht nötig.

### Abschluss Grafik-Meilenstein
- Implementierungscommit: b69b353, erfolgreich gepusht.
- GitHub Actions vollständig grün, einschließlich echtem Shader-Rendering,
  Screenshot-Artefakten, Compose-Validierung und Container-Smoke-Test:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38303574178
- Keine offenen Implementierungsfehler. Die bereits vorhandene lokale Szenen-UID-
  Änderung bleibt erhalten und uncommitted. Nach pull Godot-Spiel neu starten/F5.

## Rollen-/Aktivitäts-Meilenstein — Echte Backend-/Frontend-Zusammenarbeit
- Nutzerauftrag: feste Backend-/Frontend-Agenten und deutlich sichtbare echte Aktionen.
- Ada=Backend, Turing=Frontend in Snapshots, Jobmetadaten und tatsächlichem Codex-Prompt.
- CLI-Observer liefert sichere Frameworknamen, RUNNING/PASS/FAIL und Exitcode;
  Fehltests werden je Framework geführt, andere grüne Frameworks verdecken sie nicht.
  Dateiänderungen über Shell werden zusätzlich anhand begrenzter Metadaten-Snapshots
  erkannt; keine Rohbefehle/Argumente, Pfade oder Datei-Inhalte veröffentlicht.
- Public-Message-Helper in .cafe, validierte/korrelierte Outbox→Inbox-Zustellung,
  ein echter Antwortlauf beim anderen Agenten, bis vier Warteschlangenplätze,
  keine rekursive Antwortschleife. Fehlende öffentliche Antwort wird als Fehler erkannt.
  Keine Netzwerkfreigabe oder Sandbox-Umgehung erforderlich. Artefakte begrenzt,
  Symlink-Escapes abgewiesen, private Prompts weiterhin nicht geloggt.
- API request_reply optional (standardmäßig false), native UI fordert eine echte
  Antwort an. Nach erfolgreicher Arbeit tatsächlicher Idle-Zustand nach 3 Sekunden.
- Geändert: Backendmodelle/Bus/Jobs/API/Observer, messaging.py, Simulator,
  Backendtests, collaboration_smoke.py/-smoke.sh und Protokoll-/Agentendokumentation.
- Tests: scripts/check.sh vollständig grün, 68 pytest-Tests, Godot Import/Zustände/
  Headless/Livetest, Aufgaben-/Abbruch-E2E und Reconnect. Fixtures ohne externe LLMs.
- Tatsächlich ausgeführt: scripts/collaboration-smoke.sh mit ZWEI echten Codex-Läufen;
  Backend→Frontend-API-Vertrag und echte Antwort→Backend, beide Inboxdateien und
  Aufgabenabschlüsse geprüft: Real backend/frontend collaboration smoke: PASS.
  scripts/codex-smoke.sh für tatsächliche Dateiänderung/unittest ebenfalls PASS.
- Offene Schritte: 4K-UI/Grafik separat committen und finalen Grafik-CI-Lauf prüfen.
- Commit-ID: `git log --format='%h %s' --grep='implement agent roles and real CLI collaboration'`.

### Rollen-Meilenstein — Warteschlangen-Abschluss
- Rollen-/CLI-Implementierung 1800b93 erfolgreich gepusht.
- Gleichzeitige Nachrichtenversendung serialisiert; volle Antwortqueue lehnt neue
  Anfragen mit HTTP 429 ab, ohne ältere Fragen zu verlieren. Zustellfehler erscheinen
  als tatsächliche Fehler; öffentliche Antworten werden anhand erfolgter Zustellung geprüft.
- Geändert: jobs.py, main.py, test_roles_messaging.py, docs/agent-roles.md.
- Validierung: vollständige scripts/check.sh-Kette grün, 69 pytest-Tests plus
  Godot-/Integrationsprüfungen. Zusätzlicher Regressionstest für Queue-Überlauf.
- Commit-ID: `git log --format='%h %s' --grep='preserve queued peer requests under concurrent delivery'`.
