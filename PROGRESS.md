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

## 4K-/Aktions-Meilenstein — UHD und sichtbare echte Agentenaktionen
- Nutzerauftrag vollständig umgesetzt: 3840×2160 (4K UHD, 16:9) als tatsächlicher
  fester Render-Viewport; Startfenster 1920×1080, F11 für Vollbild.
- Rollen an Figuren, Arbeitsplätzen, Dialog und Karten: Ada Backend, Turing Frontend.
  Coding/CLI-Test/CLI-Befehl/Chat/Response/Idle/DONE/ERROR gut sichtbare Figuren-Badges,
  Tastatur-/Terminal-/Sprechblasen-/Kaffeeanimationen, passende Stationswege.
  Private Modellantwort ohne Empfänger wird als Response statt Peer-Chat gezeigt.
- Zwei Aktivitätskarten mit aktuellem autoritativem Zustand und bis fünf tatsächlich
  beobachteten Einträgen inkl. Zeit, Framework, RUNNING/PASS/FAIL; Reconnect beginnt
  ehrlich beim Snapshot. Figuren dürfen begrenzt vergangene echte Events nachspielen.
- Grafik weiter verbessert: eigenes Distance-Field-UI-Fontresource für scharfe 4K-
  Schrift, Blattpolygone, Regal-/Messingdetails, zusätzlicher Kaffee-Dampf-Shader,
  reale Testaktivität steuert Testmonitor. Atmosphere schaltet alle fünf Effekte.
- Geändert: game/project.godot, cafe.gd, activity_card.gd, character.gd,
  event_state.gd, world.gd, steam.gdshader, test_states.gd, CI-Renderauflösung,
  README.md, docs/graphics.md und gerenderte 4K-Vorschau.
- Vorhandene lokale Szenen-UID-Änderung in game/scenes/cafe.tscn weiter erhalten,
  nicht gestagt. Private Laufzeit-/Kommunikationsdaten nicht ins Repository übernommen.
- Prüfungen: scripts/check.sh komplett grün, 69 pytest-Tests einschließlich
  Rollen, echte Helper-Zustellung mit Fixture-Antwort, fehlende öffentliche Antwort,
  volle Antwortqueue, Shell-Code-Änderungen und Datenschutz; Godot Import/Zustände,
  Headless, Aufgaben-/Kommunikations-/Abbruch-E2E, Backend-Reconnect und Demo-Livetest.
- Tatsächlicher 4K-OpenGL-Render über Godot 4.4.1 Compatibility/Mesa llvmpipe PASS;
  Vorschauen mit/ohne Shader und Dialog visuell geprüft. Bei globalem Fontwechsel
  fehlerhafte Labelabstände erkannt, durch eigenes UI-Fontresource behoben.
  Keine Shader-/Scriptfehler; virtuelle VSync-/D-Bus-Warnungen ohne Funktionseinfluss.
- Live-Proben aus Rollen-Meilenstein: echter Codex-Code/unittest PASS und zwei echte
  Backend-/Frontend-Codex-Läufe mit gegenseitiger Nachrichtenzustellung PASS.
- Commit-ID: `git log --format='%h %s' --grep='render cafe in 4K with visible role-based agent actions'`.
- Offene Prüfung: finalen GitHub-Actions-Lauf bestätigen; Windows-GPU-Leistung
  nicht gemessen. Nutzer lädt Branch, startet Backend für neue Rollenlogik erneut
  und öffnet Godot/F5 (F11 bei 4K-Monitor); keine neuen Python-Abhängigkeiten nötig.

### Abschluss 4K und Rollen-Aktionen
- Rollen-/Zusammenarbeitscommit: 1800b93; Queue-Korrektur: b9db572;
  4K-/Aktionsansicht: 651c788. Alle erfolgreich gepusht.
- Finale GitHub Actions vollständig grün: Unit-/Integrations-/Godot-Checks,
  echter 4K-Shader-Render, Screenshot-Artefakte, Compose und Container-Smoke:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38310655093
- Beide echten Codex-Smokes bestanden; keine offenen Implementierungsfehler.
- Nutzer: Branch pullen, Backend neu starten (neue Rollenlogik), Godot-Spiel mit F5
  starten und F11 für Vollbild nutzen. Bestehende lokale Szenen-UID erhalten.

## Management M1 — Persistente Konfigurationen, Markdown-Aufgaben und Rollen
- Bestehende Architektur untersucht: FastAPI/EventBus/Codex/Godot weiterverwendet;
  bisher keine Datenbank, nur flüchtige Ausführungsmetadaten und Runtime-Volume.
- SQLite (Python-Standardbibliothek) für Registry, Zustände und Aktivitätslogs;
  lesbare JSON-Konfigurationen; Markdown-Dateien bleiben Quelle der Anweisungen.
- Validierte Agenten-/Git-/Ausführungskonfiguration; austauschbare Aufgaben und
  mehrere Rollen; genehmigter Workspace-Root, Symlink-/Traversal-Abweisung.
- Dateien: management/{config,storage,files,registry,__init__}.py und
  tests/test_management_definitions.py. Bestehende Szenen-UID bleibt ungestagt.
- Validierung: scripts/check.sh PASS, 80 pytest-Tests, Godot Import/Zustände/
  Headless/WebSocket sowie bestehende Aufgaben-/Reconnect-Integration bestanden.
- Commit-ID dieses Eintrags: git log --format='%h %s' --grep='persist agent configurations and Markdown definitions'.
- Push: gemäß neuem Nutzerauftrag nicht ausgeführt; explizite Freigabe erforderlich.
- Nächste Schritte: GitService/Worktrees, echte Dateisystemisolation, Lifecycle,
  Management-API und Godot-Oberfläche. Neue Management-Module noch nicht angeschlossen.

## Management M2 — Isolierte Workspaces, GitService und persistente Laufzeiten
- M1-Commit: 84748a7 (lokal, nicht gepusht).
- Dedicated GitService: init/connect/clone, Branchwechsel, Stage/Commit, Diff/History,
  parallele Worktrees; isolierte Git-Prozesse, argumentbasierte Befehle, keine Hooks,
  keine destruktiven Operationen, Remote-Opt-in und ausdrückliche Einzelbestätigung.
- Bubblewrap-Mount-/PID-/IPC-/UTS-Isolation zusätzlich zum Codex-Sandbox;
  genehmigter Workspace, readonly Git-Metadaten und Markdown-Snapshots; kein Zugriff
  auf andere Workspace-Dateien, Controller-Daten oder SSH-Sockets durch Agenten.
- Ausführungsspezifischer Git-Helper erlaubt Agenten Stage/Commit auf ihrem Worktree,
  ohne Git-Metadaten frei schreiben oder Remote-Credentials erhalten zu müssen.
- Persistente Lifecycle-/Task-/Abnahmestatus, Logs/Hashes, Timeout/Abbruch/Retry,
  Restart-Recovery; Workspace-Sperren, eigener Verwaltungstoken und Legacy-API-
  Bypassschutz während verwalteter Ausführungen. Erfolgreicher Prozess != Aufgabenabnahme.
- Dateien: management/{git,sandbox,execution,api,security,git_helper}.py,
  main.py/config.py, test_management_git.py/test_management_execution.py,
  Dockerfile, Compose/SSH-Override und CI-Bubblewrap-Installation.
- Validierung: scripts/check.sh vollständig PASS, 91 pytest-Tests einschließlich
  aktueller (für M3 vorbereiteter) nativer Godot-Verwaltungsintegration; Godot
  Import/Zustände/Headless/WebSocket/Tasks/Abbruch/Restart bestanden. Keine Skips.
- Echte Namespace-Tests: fremde Dateien unsichtbar, Git-Metadaten und Markdown
  tatsächlich schreibgeschützt. Temporäre Repo-/Worktree-/Commit-Integration PASS.
- Echter Codex-Probelauf: Markdown/Python-Code/unittest/Git-Helper-Commit PASS;
  Funktion und Tests unabhängig erneut geprüft, nur Agenten-Branch geändert.
  Ein gewöhnlicher CLI-Fehler wurde vom Modell behoben; Test-/Runtimeabschluss
  sowie unabhängige Prüfung waren erfolgreich. Keine Remote-Git-Operation.
- Compose/CI YAML lokal geparst und Mounts/Loopback geprüft. Docker CLI/Daemon
  hier nicht vorhanden; Image-Rebuild und Compose-Start daher nicht lokal getestet.
- Commit-ID: git log --format='%h %s' --grep='isolate managed agents and coordinate Git worktree execution'.
- Push: nicht ausgeführt (neueste Nutzeranweisung). Nächster Meilenstein: native
  Godot-Verwaltung, Beispiele, ausführbare Dokumentation und finaler Regressionstest.

## Management M3 — Native Verwaltung, Konfigurationsbeispiele und Ende-zu-Ende-Nachweis
- Backend-/Isolation-Meilenstein: 84abb98; Registry-/Markdown-Meilenstein: 84748a7.
- Godot-Panel: Agenten erstellen/editieren, Workspace/Task/mehrere Rollen auswählen,
  Git/Timeout/Retry konfigurieren, Markdown-Editor, Workspace-/Git-Verwaltung,
  Start/Stop/Restart, Status/live Logs, Ausführungshistorie und separate Aufgabenabnahme.
- Zusätzliche Figuren folgen demselben echten Eventstream und öffnen beim Anklicken
  ihre Konfiguration. Bestehende Ada-/Turing-Karten, Demo und Task-UI bleiben erhalten.
- Sicherheit nach Prüfung ergänzt: exklusiver Controller-Lock vor Recovery,
  HTTP-Verwaltungstoken nicht im Worker verfügbar, einzelne Dateipfade statt Verzeichnis-
  Staging (keine versehentliche Aufnahme von .env/.cafe), read-only Markdown-Snapshots,
  Abnahme bleibt an exakte Aufgabenfassung gebunden; Restart auch nach Abschluss.
  Git-Remotes lassen sich ohne Netzwerkaufruf konfigurieren; Auswahl pro Agent.
- Neu: management.gd/.uid, test_management.gd/.uid, native Godot-/Backend-Fixture,
  test_game_management.py, docs/agent-management.md, examples/backend-agent.json,
  vier Rollenbeispiele und Beispieltask; management_smoke.py/-smoke.sh.
- Geändert: cafe.gd/character.gd/event_state.gd/test_states.gd, README und Architektur,
  main.py/management APIs/Execution/Git und passende Regressionstests.
- Tests: scripts/check.sh PASS, 93 pytest-Tests ohne Skips; Godot Import/Zustände/
  Headless sowie reale HTTP/WebSocket/Verwaltungs-/Aufgaben-/Abbruch-/Reconnect-Integration.
- Echte Codex-Probe erneut PASS: eingefrorene Markdown-Aufgabe, isolierter Worktree,
  tatsächliche Python-Codeänderung, unittest, Git-Helper Stage/Commit; unabhängige
  Funktions-/Testprüfung und zwei Commits nur auf Agenten-Branch. Keine Remote-Aktion.
- Compose/CI-YAML parse PASS. Lokaler Container-Rebuild und neuer GPU-UI-Render
  nicht ausgeführt (Docker/Xvfb hier nicht verfügbar); native Oberfläche headless geprüft.
- Bekannte Grenzen: Linux/Bubblewrap mit funktionierenden Namespaces; ein Controller;
  keine automatische Aufgabenabnahme/Merges, Remote-Git standardmäßig deaktiviert;
  Legacy Ada/Turing bleibt vertrauensbasierter Kompatibilitätspfad.
- Commit-ID: git log --format='%h %s' --grep='add native agent management and verified execution workflow'.
- Push/Merge nicht ausgeführt; Nutzerfreigabe für Push fehlt gemäß neuester Vorgabe.
- Nächste Schritte beim Nutzer: Backend neu bauen, Verwaltungstoken lokal lesen,
  Godot/F5 → Manage agents, Workspace/Rollen/Task konfigurieren; vollständige Anleitung
  und Dateiliste stehen in docs/agent-management.md.

### Abschluss Management-Erweiterung
- Implementierungscommits: 84748a7 (Registry/Markdown), 84abb98 (Isolation/Git/
  Lifecycle), 360127b (Godot-Verwaltung, Beispiele, Sicherheit, Ende-zu-Ende-Workflow).
- Finale Checks: 93 pytest-Tests bestanden, Ruff und vollständige Godot-Headless-/
  HTTP-/WebSocket-/Verwaltungsintegration bestanden; echter isolierter Codex-Smoke
  mit unabhängig geprüften unittest/Funktion/Agenten-Commit bestanden.
- Keine Pushes, Merges, Änderungen an Credentials oder destruktiven Git-Operationen.
  Einzige verbleibende lokale Änderung: vorherige Nutzer-UIDs in game/scenes/cafe.tscn.
- Für den Nutzer bereit: docs/agent-management.md inklusive aller geänderten/neuen
  Dateien, Start-/Token-/Workspace-/Git-Anleitung, Konfigurationsbeispiel und Grenzen.
- Noch extern zu prüfen: frisch gebautes Docker-/Podman-Image und Darstellung auf
  der Windows-GPU. Neues Backend und Genehmigung für Push sind separate nächste Schritte.

### Snapshot-Grenzprüfung
- Abschließende Prüfung großer Rollenzuweisungen: sichtbare Rollen-Zusammenfassung
  auch beim Start auf 120 Zeichen begrenzt; vollständige 16 Rollen bleiben in der
  persistenten Konfiguration erhalten. Verhindert übergroße WebSocket-Snapshots.
- Neuer Regressionstest prüft tatsächlichen Start, Snapshot-Budget und Rollenpersistenz.
- Finale Validierung nach dieser Korrektur: scripts/check.sh, 94 pytest-Tests und
  sämtliche Godot-/Integrationsprüfungen bestanden. Commit-ID: git log --format='%h %s'
  --grep='bound managed role summaries in realtime snapshots'. Kein Push.

## GUI M1 — Übersichtliche Oberfläche und tatsächliche Eingabetests
- Nutzerauftrag: Verwaltungsoberfläche schöner machen, fehlerhafte Klicks beheben,
  echte GUI-Tests ergänzen. Kein Push gemäß fortgeltender letzter Nutzeranweisung.
- Neue Karten, Mint-Aktionen, konsistente Labels/Abstände, separate Scrollbereiche,
  fixierte Agentenaktionsleiste, lesbare Listen/Details und 4K-Dropdowns.
- Behoben: verlorene Klicks während HTTP-Polls, zurückgesetzte Auswahl, verschwundene
  Fehlerhinweise, Überschreiben neuer Eingaben durch verspätete Save-Antworten,
  doppelte Submits und fehlende Auswahl nach Agentenerstellung. Aktionen anhand
  Backend-Capabilities/Lifecycle deaktiviert; verständliche lokale Validierung.
- Café: Klickposition aus InputEvent statt Cursor-Polling; neuer Taskdialogstil,
  gemeinsamer Pending-/Offline-Zustand aller Aktionen, modale Hintergründe und Escape.
- Echte GUI-Szenarien: MouseMotion/Press/Release, Tastatur, Dropdowns/Tabwechsel,
  verzögerte HTTP-Anfragen, Markdown/Rollen, Create/Edit/Start/Stop, Logs/Review,
  Git init/branch/stage/commit/diff und originale Avatar-/Task-/Nachrichten-/Cancel-Klicks.
- Dateien: management.gd, cafe.gd, character.gd, project.godot, Management-API-
  Capabilities; GUI-/Café-Input-/Render-Skripte und UIDs, Backend-Testharness/Fixture,
  bestehender Managementtest, CI sowie docs/gui-testing.md und Vorschau.
- Validierung: vollständige scripts/check.sh PASS, 96 pytest-Tests inkl. beider
  Input-Szenarien und aller bisherigen Tests; Godot Import/Zustände/Headless/Live PASS.
  Gerenderter OpenGL-GUI-Test zusätzlich PASS (Mesa llvmpipe, fester 4K-Viewport).
- Vorschauen aller vier Seiten und Dropdowns tatsächlich gerendert und visuell
  geprüft; zu kleine/abgeschnittene Popup-Schrift erkannt und Dimensionen korrigiert.
  Der neue Taskdialog wird zusätzlich gerendert. Vorschauen verwenden Beispieldaten.
- Neue Änderungen an Test-Randfällen (Validation/Poll/Doppelklick) nochmals durch
  Abschlussprüfung abgesichert. Keine echten LLM-Aufrufe für diese GUI-Tests nötig.
- Commit-ID: git log --format='%h %s' --grep='polish cafe management and test real GUI input'.
- Grenzen: Windows-DPI/GPU noch nicht auf Zielgerät getestet; CI aktualisiert, aber
  mangels Push hier noch nicht auf GitHub gelaufen. Vorhandene Szenen-UID ungestagt.

## Setup M1 — Lokaler Projektstarter und Team-Assistent
- Nutzerauftrag: Inbetriebnahme mit Auswahl eines bestehenden Git-Projektordners
  vereinfachen; Codex und SSH für zwei Agenten anbinden.
- Architektur: vorhandene Registry, MarkdownManager, GitService, Sandbox und
  SQLite weiterverwendet. ProjectSetup ergänzt geschützte Projekt-/Check-/Team-
  Endpunkte; keine neue Datenbank und keine freie Hostpfad-API.
- Starter scripts/setup-project.py: nativer Ordnerdialog mit Terminal-Fallback,
  gezielter Compose-Bind-Mount, kollisionsarme Projekt-ID, SSH-Agent/known_hosts
  ohne private Schlüssel, Codex-Anmeldung, Healthcheck, Godot-/WSL-Start mit Token
  ausschließlich im Prozessspeicher. Privileged-/Remote-Optionen explizit.
- Godot: Setup-Seite mit Zielbeschreibung, Prüfbericht, fest sichtbaren Aktionen,
  automatischem Öffnen/Vorauswahl durch Starter und Frontend-/Backend-Team.
- Teamerstellung: echte getrennte Worktrees/Branches, editierbare Markdown-Aufgaben
  und Rollen, persistente Projektzuordnung, Wiederaufnahme unterbrochener Schritte
  und Erhalt nachträglicher Änderungen. Keine automatischen Agentenstarts,
  initialen Commits, Pushes oder Merges. Uncommittete Quelldateien bleiben erhalten.
- Geänderte/erstellte Dateien: management/setup.py, api.py, git.py,
  scripts/setup-project.py, game/scripts/management.gd, Setup-Input-Test und UID,
  Render-Preview-Skript, Backend-Setup-/Launcher-/GUI-Tests und Fixture, CI,
  README.md, docs/project-setup.md, docs/agent-management.md, Setup-PNG.
- Tests: scripts/check.sh mit 105 pytest-Tests, Ruff/Format sowie Godot-Import,
  Zustands-, Headless- und Live-WebSocket-Prüfungen. Zusätzlicher gerenderter
  OpenGL-Setup-Klicktest bestanden; tatsächliche 4K-Vorschau visuell geprüft.
  Testdaten verwenden temporäre Git-Repositories; Codex-Login wird im Fixture
  ersetzt, keine Modellkosten und keine externen Git-Operationen im Testlauf.
- Grenzen: Docker-Hostlauf, nativer Ordnerdialog und Windows-/WSL-Godot-Übergabe
  benötigen Zielhostprüfung; hier keine Docker-CLI verfügbar. Ein externes
  Quellprojekt pro Starterlauf, bestehendes Hauptrepository/initialer Commit nötig.
  Remote-Prüfung belegt nur lesenden Zugriff, keine Push-Berechtigung.
- Commit-ID: git log --format='%h %s' --grep='add guided project and agent setup'.
  Kein Push gemäß fortgeltender Nutzeranweisung. Vorhandene Nutzeränderungen an
  game/project.godot und game/scenes/cafe.tscn bleiben ungestagt.
- Nächste Schritte: Hostlauf anhand docs/project-setup.md; automatische Aufgaben-
  abhängigkeiten und Integration der getrennten Branches sind weiterhin separat.

## Setup M2 — Native Dateiauswahl und gemeinsame Projekt-Markdown-Dateien
- Nutzerauftrag: AGENTS.md/PLANNING.md im Assistenten nutzen und Dateien/Projekt
  über Windows-Dialoge auswählen. SSH-Schlüsselauswahl auf Nutzerkorrektur entfernt;
  bestehendes SSH-Agent-Forwarding bleibt unverändert.
- Starter: unter WSL nativer Windows-Ordnerdialog über konstanten PowerShell-Code,
  UTF-8-Ausgabe und wslpath-Argumentübergabe ohne interpolierte Benutzereingaben.
- Godot: native Markdown-Dateiauswahl, Import zur Vorschau im Editor, explizites
  Laden/Speichern für AGENTS.md/PLANNING.md und Vorlagen für fehlende Dateien.
  Der Import allein schreibt keine Projektdatei und überträgt keinen lokalen Pfad.
- Backend: feste Dokumentnamen, Unterstützung existierender Kleinbuchstaben-Dateien,
  12-KiB-Limit, Symlink-/Pfadschutz, SHA-256-Konfliktprüfung und Schreibsperre bei
  laufenden Projektagenten. Windows-UTF-8-BOM wird unterstützt.
- Runtime: beide Agenten erhalten vor jedem Lauf aktuelle Projektdateien aus dem
  Quellrepository als schreibgeschützte Snapshots unter .cafe/instructions/project/.
  Uncommittete Quelldateien funktionieren auch mit älteren Worktrees. Hashes werden
  je Lauf gespeichert; vorherige Snapshots bleiben erhalten. System-Sicherheit und
  validierte Konfiguration haben weiter Vorrang vor Markdown-Anweisungen.
- Dateien: scripts/setup-project.py, management/project_documents.py, api.py,
  execution.py, setup.py, game/scripts/management.gd, Setup-Input-/Render-Test,
  Backend-Dokument-/Starter-/GUI-Tests, Setup-/Management-Dokumentation und Vorschau.
- Validierung: scripts/check.sh mit 113 pytest-Tests plus Ruff/Format, Godot-Import,
  Headless-, Zustands- und Live-WebSocket-Prüfungen. Gerenderter OpenGL-Setup-Test
  zusätzlich bestanden. Echte GUI-Eingaben prüfen Dateidialog, Import ohne Schreiben,
  explizites Speichern beider Dateien und erneutes Laden. Namespace-Test bestätigt
  schreibgeschützte Snapshots für beide Agenten; Konflikt-/Alias-/BOM-Tests bestanden.
- Grenzen: nativer Windows-Dialog und vollständiger WSL/Docker-Hostlauf sind hier
  nicht direkt ausführbar. Der Dialogvertrag ist getestet; GUI-Automatisierung nutzt
  den eingebetteten Godot-Dateidialog. Keine realen Modellaufrufe für diese Tests.
- Commit-ID: git log --format='%h %s' --grep='add project instruction editors and native file selection'.
  Feature-Branch wird gemäß Freigabe synchronisiert; kein weiterer Main-Merge.
  Vorhandene Änderungen in game/project.godot und game/scenes/cafe.tscn bleiben lokal.

## Setup M3 — Sichtbare Projektprüfung und Freischaltung aus dem Projektplan
- Nutzerfehlerbericht: Check project wirkt ohne Reaktion, Team-Erstellung bleibt
  gesperrt trotz geladener Projektdateien.
- Reproduziert: ausstehende Anfragen verändern den Prüfbericht nicht; HTTP-Fehler
  erscheinen nur in einer schmalen, gekürzten Kopfzeile. Neuer echter GUI-Test
  scheiterte vor der Korrektur an fehlender unmittelbarer Prüf-Rückmeldung.
- Godot: sofortiges Checking-Feedback, dauerhaft sichtbarer Status oberhalb des
  Scrollbereichs, vollständige Fehlermeldung im Prüfbericht, Timeout-Erklärung,
  lesbare Gründe für gesperrte Team-Erstellung. Fehler löschen keine Markdown-Edits.
- Leeres Ziel mit geladener PLANNING.md verwendet deren nächsten offenen Meilenstein
  als Auftrag; kurzer ausdrücklich eingegebener Text bleibt validierungspflichtig.
  Team-Erstellung verlangt weiterhin erfolgreiche Sandbox-/Codex-/Git-Prüfungen.
- Zusätzlich reproduzierter Git-Fehler: abweichender Repository-Eigentümer wird bei
  eingebundenen Host-Projekten abgelehnt. GitService setzt safe.directory nur für
  den jeweils validierten Workspace, nur pro Prozess, ohne globale Änderung oder
  Wildcard. Echter Git-Test mit simulierter abweichender Ownership war zuvor rot
  und prüft nun Repository-Information sowie Worktree-Erstellung erfolgreich.
- Backend: gesamte Prüfung auf 30 Sekunden begrenzt; Git-Inspektionsfehler ergeben
  einen strukturierten FIX-Bericht. Prozessbereinigung bleibt erhalten.
- Dateien: game/scripts/management.gd, game/tests/test_setup_input.gd,
  management/setup.py und git.py, Backend-Setup-/Git-Tests, GUI-Fixture,
  docs/project-setup.md, PROGRESS.md.
- Tests: scripts/check.sh PASS, 116 pytest-Tests, Ruff/Format, Godot-Import,
  Headless-/Zustands-/Live-WebSocket-Prüfungen. Separater OpenGL-Setup-GUI-Test PASS.
  GUI deckt verzögerte Prüfung, tatsächliche 409-Antwort, sichtbaren Fehler,
  erneute erfolgreiche Prüfung und Team-Erstellung allein aus dem geladenen Plan ab.
- Grenzen: konkrete Host-Ursache des Nutzers ist ohne dessen Laufzeitbericht noch
  nicht bestätigt; Windows-/Docker-Zielhostlauf hier nicht ausführbar. Der neue
  Bericht macht fehlende Voraussetzungen sichtbar, umgeht sie aber nicht.
- Commit-ID: git log --format='%h %s' --grep='fix project setup feedback and plan-based team creation'.
  Feature-Branch wird synchronisiert; kein automatischer Main-Merge.

## Setup M4 — Sandbox-Ursachen und übersprungene Folgeprüfungen
- Fortsetzung des Nutzerproblems: Namespace-Sandbox blockiert, gleichzeitig wird
  fälschlich eine nicht geprüfte Codex-Anmeldung als Fehler angezeigt.
- Gemeinsamer begrenzter Sandbox-Selbsttest für Setup und Workerstart: feste
  Fehlerkategorien für Namespace-Rechte, Ressourcen, Mounts, fehlende Laufzeit und
  Zeitlimit. Kein Auth-Mount/Modellaufruf; rohe stderr-Inhalte gelangen nicht in API
  oder Aktivitätslogs. Begrenzte Ausgabe und Prozessgruppen-Bereinigung getestet.
- Setup zeigt Codex und Git nach Sandbox-Fehler als SKIPPED/SKIP; keine irreführende
  Aufforderung zur Neuanmeldung. Unsafe Starts bleiben weiterhin gesperrt.
- Starter führt nach Healthcheck die Diagnose am ausgewählten Projektmount aus;
  bei Fehlern hält er vor Codex-Login und Godot an. Keine automatische Ausweitung
  von Rechten und kein Fallback ohne Isolation.
- scripts/sandbox-diagnostics.py liefert teilbare JSON-Diagnose mit festen
  Kategorien und verfügbaren numerischen Namespace-Einstellungen. Dokumentation
  beschreibt expliziten Privileged-Start und Diagnose im bestehenden Container.
- Dateien: management/sandbox.py und setup.py, scripts/setup-project.py und neues
  sandbox-diagnostics.py, game/scripts/management.gd, neuer blockierter GUI-Test
  samt UID, Backend-Sandbox-/Starter-/Setup-Tests und Fixture, docs/project-setup.md.
- Validierung: scripts/check.sh PASS mit 128 pytest-Tests, Ruff/Format, Godot-Import,
  Headless-/Zustands-/Live-WebSocket-Prüfungen; gerenderter OpenGL-Test der blockierten
  Sandbox PASS. Aktueller echter Namespace-Selbsttest liefert hier code=ready.
  Nach präzisierter Workspace-Argumentübergabe alle 12 Starter-/Setup-Tests erneut PASS.
- Grenze: im Entwicklungscontainer steht keine Docker-CLI bereit. Konkrete
  Docker-/WSL-Hostrichtlinie des Nutzers bleibt ohne dessen Diagnose unbekannt;
  insbesondere beweist ein lokales ready nicht die Funktionsfähigkeit seines Hosts.
- Commit-ID: git log --format='%h %s' --grep='diagnose sandbox startup and skip dependent checks'.
  Feature-Branch wird synchronisiert; kein automatischer Main-Merge.

## Setup M5 — Tatsächlichen Codex-Anmeldestatus korrekt prüfen
- Nutzerbericht: Namespace, Modus und Git bestehen; Codex bleibt als einziger FIX.
- Konkreter Programmfehler reproduziert mit codex-cli 0.162.1: die Prüfung rief
  codex --ignore-user-config login status auf. Diese Option ist nur für exec
  gültig; der Statusaufruf beendet sich vor der Auth-Prüfung mit Parserfehler.
- Korrektur: codex login status innerhalb der bestehenden Auth-Sandbox. Keine
  Änderung an Zugangsdaten, Host-Konfiguration oder an exec --ignore-user-config.
  Die Sandbox bindet weiterhin nur auth.json, nicht die Benutzerkonfiguration ein.
- Regression mit echter CLI statt Status-Stub: temporäres, klar fiktives Auth-File,
  Namespace ohne Netzwerk, vollständige Projektprüfung mit und ohne Auth-Datei.
  Test scheitert vor der Korrektur und besteht danach; keine Modellaufrufe.
- CI installiert dieselbe gepinnte CLI 0.162.1 wie das Dockerfile, damit dieser
  Regressionstest dort ausgeführt und nicht wegen fehlender CLI übersprungen wird.
- Dateien: management/setup.py, backend/tests/test_project_setup.py,
  .github/workflows/ci.yml, docs/project-setup.md, PROGRESS.md.
- Validierung: scripts/check.sh mit 129 pytest-Tests, Ruff/Format und bisherigen
  Godot-Import-/Headless-/Zustands-/Live-WebSocket-Prüfungen. Der isolierte echte
  CLI-Regressionslauf bestand sowohl mit als auch ohne gespeicherte Test-Anmeldung.
- Grenze: gespeicherte Auth wird geprüft, nicht die serverseitige Gültigkeit eines
  Kontos oder Modellverfügbarkeit. Nutzer-Anmeldung wurde nicht gelesen/geändert.
- Commit-ID: git log --format='%h %s' --grep='use supported Codex login status command'.
  Feature-Branch wird synchronisiert; kein automatischer Main-Merge.

## Worker M6 — Sichtbare Aktivität, Git-Fehler und erhaltene Ergebnisse
- Kurze, zentrierte Figurenbeschriftung (Backend/Frontend; andere Namen maximal
  18 Zeichen). Große Karten und Arbeitsplätze folgen den eingerichteten Workern;
  deren unbenutzte Ada/Turing-Platzhalter werden ausgeblendet. Unveränderte
  Snapshots setzen die Animation nicht mehr zurück; STARTING hat eine Animation.
- Gespeicherte Abschluss-/Fehlerzustände werden nach Neustart wieder angezeigt.
  Git-Vorbereitungsfehler erreichen den Eventstream und bleiben im Agentenstatus.
  Teamkonfiguration wird vor Git-Vorbereitung gespeichert, auch bei Teilfehlern;
  die Einrichtung bleibt wiederaufnehmbar und erhält bestehende Arbeitsdateien.
- Git-Fehler nennen Operation und klassifizierte Ursache (Branch-Konflikt,
  Rechte, Locks, Metadaten, SSH); rohe stderr-Ausgaben werden nicht veröffentlicht.
  Die konkrete Ursache im Nutzercontainer ist ohne die neue Diagnose noch unbekannt.
- Ergebnisordner im Ausführungsdialog verdeutlicht; docs/project-setup.md erklärt
  persistente Worktrees, Kopieren der Dateien und Unterschiede zum Quellprojekt.
- Dateien: management/{git,execution,setup}.py; deren drei Backend-Testdateien;
  game/scripts/{cafe,character,management}.gd; game/tests/{test_states,test_management}.gd;
  docs/project-setup.md und PROGRESS.md.
- Validierung: scripts/check.sh PASS: 131 pytest-Tests, Ruff/Format, Godot-Import,
  Zustands-, Headless- und Live-WebSocket-Tests. Nach erweiterter Speicherung vor
  Git-Vorbereitung: 13 Setup-Tests erneut PASS, inklusive frischem Controller auf
  derselben SQLite-Datei und erhaltener Konfiguration/Rollen/Aufgaben nach Fehler.
- Git-Commit-ID: git log --format='%h %s' --grep='preserve worker setup and show managed activity'.
- Nächster Schritt: explizit gewünschtes Hochladen auf eigene Agenten-Branches;
  dies war bisher absichtlich gesperrt und wird separat implementiert/getestet.

## Worker M7 — Ergebnisse auf eigene Git-Branches veröffentlichen
- Nutzer präzisiert: Die von Workern bearbeiteten Projektdateien sollen auf das
  Projekt-Remote hochgeladen werden. Vorheriger Meilenstein: cd27365.
- Opt-in im Starter (--publish-results), Setup (publish_results) und pro Agent
  (allow_push + push_on_success). Bestehende Teams können freigeschaltet werden,
  ohne Aufgaben, Rollen, Arbeitsdateien oder Referenzen auf frühere Läufe zu verlieren.
- Worker erhalten Commit-Anweisungen für den bestehenden privaten Git-Helper.
  Nach Runtime-Erfolg pusht ausschließlich der Controller die committierten
  Ergebnisse. Uncommittete Projektänderungen verhindern einen irreführenden Upload.
- GitService prüft eigene agent/<id>/…-Branch und genau eine freigegebene SSH-/HTTPS-
  Push-URL ohne Zugangsdaten. Explizite einzelne Refspec, kein Force/Mirror/Tags,
  kein Submodul-Push. Auch der manuelle Push nutzt denselben Service.
- publication und ggf. Remote-Name/Branch/Commit werden separat persistiert und
  im Ausführungsdialog angezeigt. Runtime-Erfolg und Aufgabenabnahme bleiben
  getrennt. Abgelehnte Pushes erhalten Dateien und melden FAILED statt Erfolg.
- Korrigierte Diagnose unterscheidet lokale Dateirechte von SSH-Authentifizierung
  und nicht vorspulbaren Remote-Branches; keine rohen Git-Ausgaben im API-Fehler.
- Demo bleibt trotz gespeicherter Worker benutzbar; bei paralleler Legacy-Nutzung
  bevorzugen die Karten die zuletzt beobachtete Aktivität derselben Rolle.
- Dateien: management/{api,config,execution,git,registry,setup}.py;
  scripts/setup-project.py; game/scripts/{management,cafe}.gd;
  Tests: test_worker_publication.py, test_management_git.py, test_project_setup.py,
  game/tests/{test_setup_input,test_management}.gd;
  docs/{project-setup,agent-management}.md, examples/backend-agent.json, PROGRESS.md.
- Validierung: scripts/check.sh vollständig PASS mit 141 pytest-Tests,
  Ruff/Format, Godot-Import, Zustands-, Headless- und Live-WebSocket-Prüfungen.
  Zusätzlicher gerenderter OpenGL-Setup-Maus-/Tastaturtest unter Xvfb PASS;
  zusätzlicher Godot-Managementtest mit Demo-Umschaltung PASS.
- Echte lokale Git-Integration gegen temporäres Bare-Remote: Worker-Commit wird
  übertragen; uncommittete Dateien blockieren Push; konkurrierende Remote-Commits
  werden nicht überschrieben. Keine externen Git-Hosts oder Modellaufrufe in Tests.
- Grenze: SSH-/Schreibrechte im Nutzercontainer für SimulationWorld konnten hier
  nicht geprüft werden. Hochladen auf Agenten-Branches ist implementiert, PR-Erstellung
  und Merge erfolgen weiterhin bewusst auf GitHub; keine automatische Integration.
- Git-Commit-ID: git log --format='%h %s' --grep='publish successful worker results to agent branches'.
  Push erfolgt auf feat/virtual-agent-cafe-mvp; Main bleibt unverändert.

## Darstellung M8 — Teststation-Beschriftung freistellen
- CLI TEST LAB von der Höhe der Bar-Dekoration auf ein eigenes dunkles Schild
  direkt über dem Testmonitor verschoben. Text anhand der tatsächlichen Schrift-
  breite zentriert; kein Überlappen mit Kerze, Dekoration oder Dampf.
- Dateien: game/scripts/world.gd und PROGRESS.md.
- Sichtprüfung: echte OpenGL-Aufnahmen unter Xvfb mit aktivierten und deaktivierten
  Effekten erzeugt und geprüft; vollständiger Text auf kontrastreichem Hintergrund.
  Vorschaubilder liegen nur in .runtime/lab-sign-preview und werden nicht committet.
- Automatisierte Validierung: scripts/check.sh PASS: 141 pytest-Tests, Ruff/Format,
  Godot-Import, Zustands-, Headless- und Live-WebSocket-Prüfungen.
- Git-Commit-ID: git log --format='%h %s' --grep='keep test lab title clear of cafe decorations'.
- Offene Punkte: keine für diese Beschriftung. Keine Änderung an Agenten/Git-Workflows.

## Team M9 — Automatisch integrieren, Requirements testen, Main übernehmen
- Nutzer autorisiert gemeinsame Feature-Integration und anschließende Übernahme
  nach main bei grünen Tests. Die manuelle Accept-/Reject-Oberfläche entfällt.
  Die vorherige Beschriftungskorrektur wurde als 000d79b separat gepusht.
- Setup auto_integrate ergänzt einen persistenten Integrations-/Testworker und
  aktiviert Worker-Pushes. Vorhandene Teams behalten Aufgaben und Worktrees.
- Neuer Integrationskoordinator wartet auf aktuelle erfolgreiche Worker-Pushes,
  übernimmt Remote-main und exakte Worker-Commits in einen eigenen Feature-Worktree
  und startet den bestehenden Codex-Adapter. Ereignisse kommen aus echten Läufen.
- Unveränderliche gemeinsame Requirements aus AGENTS.md, PLANNING.md und beiden
  Aufgaben werden als Snapshot gehasht. Der Testworker committet dieselben
  Requirements, Tests und validation/plan.json mit Anforderung-zu-Test-Zuordnung.
- Neues Validierungsmodul führt die deklarierten pytest/npm/Godot-Checks nochmals
  isoliert ohne Netzwerk, Modell-Anmeldung, SSH-Socket oder Git-Schreibrechte aus.
  Der Datei-RPC-Git-Helper wird vor diesen Controller-Prüfungen abgeschaltet.
- Nur der unveränderte getestete Commit darf nach Feature-Push auf main:
  Requirements-/Task-/Rollen-Snapshots müssen noch passen, Remote-main muss dem
  vorbereiteten Basiscommit entsprechen. Normaler Fast-forward-Push, kein Force,
  kein Mirror, keine Tags und kein automatisches Überschreiben des Quellordners.
- Team-/Prüf-/Promotionsstatus, Requirements-Zuordnung und Commit-Hashes bleiben
  persistent. Controller-Neustart behandelt Unterbrechung ausdrücklich; aktivierte
  Teams werden erneut geprüft. Fehler und Konflikte erhalten alle Arbeitsdateien.
  Retry team integration stößt eine erneute Prüfung an, ohne manuelle Annahme.
- Git-SSH-Erkennung nach globalen -c-Optionen korrigiert; dadurch erhält auch der
  bestehende Worker-Push den SSH-Agenten. Sanitiserte GitOperationError-Meldungen
  erscheinen jetzt im API-Fehler statt einer unbrauchbaren generischen Meldung.
- Dateien: neue management/integration.py und validation.py, management/{api,config,
  execution,git,setup}.py, main.py; game/scripts/management.gd und drei GUI-Tests;
  neuer test_team_integration.py, bestehende Ausführungs-/Publikationstests;
  README und docs/{automatic-integration,architecture,agent-management,project-setup,
  gui-testing}.md, PROGRESS.md.
- Testnachweise: echte temporäre Git-Repositories, normale Merges/Pushes und echte
  isolierte pytest-Läufe. Erfolgsfall, fehlgeschlagener Worker, rote gemeinsame
  Tests, ungültiger Plan, Merge-Konflikt, konkurrierendes main und geänderte Aufgaben
  werden geprüft. Keine externen Git-Hosts oder bezahlten Modellaufrufe nötig.
- Erster Gesamtlauf: 143 PASS/6 FAIL. Vier Fixture-Starttimeouts beim parallelen
  OpenGL-Renderer; ein Timer-Test mit fixer Pause sowie ein echter Diagnosefehler
  ("conflict" in einem Verzeichnisnamen). Diagnose auf echte Git-Konfliktmarker
  begrenzt; Timeout-Test mit tatsächlichem Runtime-Start und Abschluss synchronisiert.
  Gerenderter OpenGL-Setup-Maus-/Tastaturtest separat PASS.
- Finale Validierung: scripts/check.sh sequenziell vollständig PASS mit 149 pytest-Tests,
  Ruff/Format, Godot-Import, Zustands-, Headless- und Live-WebSocket-Prüfungen.
  Danach zusätzliche Parallelitätsregression PASS: gleichzeitig eintreffende
  Worker-Fertigmeldungen wiederholen einen fehlgeschlagenen Integrationslauf nicht.
- Grenzen: Tests belegen deklarierte Checks, keinen formalen Beweis aller Prosa-
  Anforderungen. Projektabhängigkeiten müssen in der Testumgebung verfügbar sein.
  Unaufgelöste Merge-Konflikte halten die Pipeline an. Remote-Rechte und Main-
  Branch-Schutz des Nutzerprojekts können hier nicht geprüft/umgangen werden.
- Git-Commit-ID: git log --format='%h %s' --grep='automate requirements-tested team integration to main'.
  Entwicklungsarbeit wird nur auf feat/virtual-agent-cafe-mvp gepusht; die neue
  Main-Promotion betrifft ausschließlich explizit freigeschaltete Projekt-Teams.

## Agenten gezielt löschen — 2026-10-19

- Implementiert: Delete agent im Agents-Tab mit Bestätigungsdialog, Abbrechen per
  Escape und Bestätigen per Enter. Die Figur verschwindet über den echten
  WebSocket-Snapshot; Auswahl/Formular werden aktualisiert.
- Authentifizierter DELETE-Endpunkt verlangt explizite Bestätigung. Laufende
  Agenten und aktive Teams blockieren das Löschen. Registry-Entfernung,
  Konfigurationsarchiv und Deaktivierung betroffener Team-Automatisierung erfolgen
  in einer SQLite-Transaktion; Neustart stellt gelöschte Agenten nicht wieder her.
- Projektdateien, Git-Branches/Commits, Aufgaben, Rollen und Ausführungsprotokolle
  bleiben erhalten. Die beiden eingebauten Demofiguren sind geschützt.
- Dateien: management/{api,execution,storage}.py; game/scripts/{management,cafe}.gd;
  neue backend/tests/test_agent_deletion.py und game/tests/test_agent_deletion.gd;
  test_game_management.py, test_gui_input.gd, docs/agent-management.md, PROGRESS.md.
- Gezielte Tests: drei Backendtests PASS (Neustart, Dateierhalt, echtes Git,
  Historie, Team-/Laufsperre, Authentifizierung und Bestätigung); Headless-GUI PASS;
  zusätzlicher vorhandener GUI-Lauf mit gesperrtem Delete bei laufendem Agent PASS.
  Separater gerenderter OpenGL-Test mit echten Maus-/Tastaturereignissen PASS.
- Grenzen: Löschen entfernt die aktive Agentenzuordnung, keine Arbeitsdateien oder
  Remote-Branches. Unvollständige Teams müssen ausdrücklich neu konfiguriert werden.
- Nächster Schritt: Nutzerprüfung im aktualisierten Godot-Client.
- Git-Commit-ID: git log --format='%h %s' --grep='add safe agent deletion'.
- Vollständige Abschlussprüfung: scripts/check.sh PASS — 154 pytest-Tests,
  Ruff/Format, Godot-Import, Zustands-, Headless- und Live-WebSocket-Tests grün.
  Eine bestehende Starlette/httpx-Abkündigungswarnung; keine Testfehler.

## Git-SSH innerhalb der Sandbox korrigieren — 2026-10-19

- Nutzerdiagnose: Host-SSH und Container-SSH sowie Push-Dry-run im echten
  Backend-Worktree erfolgreich; derselbe SSH-Aufruf in Sandbox bricht mit
  „No user exists for uid 1000“ ab. Kein Hinweis auf fehlende Repository-URL.
- Ursache: isoliertes Dateisystem enthielt keine passwd-Benutzerzuordnung;
  OpenSSH benötigt getpwuid bereits vor der Remote-Authentifizierung.
- Korrektur: ausschließlich für SSH-fähige Git-Sandbox /etc/passwd und /etc/group
  lesbar binden. Keine Shadow-Dateien, privaten Schlüssel oder Host-Homes.
  Git-Diagnostik erkennt diesen Fehler nun explizit statt generischer Push-Meldung.
- Dateien: management/{sandbox,git}.py, test_management_git.py,
  docs/project-setup.md und PROGRESS.md.
- Neue Regression: echtes OpenSSH -G unter UID 1000 im isolierten Offline-Prozess;
  Benutzerauflösung, schreibgeschützter Account-Mount und fehlende Shadow-/Home-
  Pfade werden geprüft. Erster Testlauf: 11 PASS/1 FAIL wegen abweichendem
  Schreibfehler (Permission denied statt Read-only); Mountschutz anschließend
  direkt mit statvfs geprüft. Blocking-Aufrufe in asyncio.to_thread verschoben.
- Nutzerumgebung: echter GitHub-Push wird hier nicht behauptet. Nach Update Backend
  über Starter neu starten; vorhandene Worktrees erhalten, fehlgeschlagene Worker
  können mit ihrem bisherigen Stand fortsetzen und erneut veröffentlichen.
- Nächster Schritt: erneuter Push in der Nutzerumgebung, danach Teamintegration.
- Git-Commit-ID: git log --format='%h %s' --grep='resolve SSH users inside Git sandbox'.
- Abschlussprüfung: scripts/check.sh vollständig PASS — 156 pytest-Tests,
  Ruff/Format, Godot-Import, Zustands-/Headless- und Live-WebSocket-Tests.
  Bestehende Starlette/httpx-Abkündigungswarnung, keine Testfehler.

## Git-Ansicht auf aktuellen Agenten-Workspace ausrichten — 2026-10-19

- Befund: load_agent aktualisierte die Agenten-Konfiguration, aber nicht die
  separate Git-Workspace-Auswahl. Alte Projekt-Mounts ohne .git konnten deshalb
  weiterhin Ziel von View diff und Inspect repository bleiben.
- Änderung: Agentenauswahl wählt dessen Workspace auch zur Git-Inspektion;
  bewusste manuelle Workspace-Auswahl bleibt möglich. Fehlender Workspace wird
  lokal abgefangen. Git-Fehler ersetzen alte Ergebnisse direkt im Git-Panel.
- Backend nennt fehlendes .git mit konkretem Hinweis auf aktuelle Worker-Worktrees,
  statt einer generischen Git-Fehlermeldung. Keine automatischen Init-/Git-Mutationen.
- Dateien: management/git.py, game/scripts/management.gd, test_management_git.py,
  game/tests/test_gui_input.gd, docs/agent-management.md und PROGRESS.md.
- Gezielte Prüfung: 14 Tests PASS, einschließlich echter Git-Integration und
  Godot-Maus-/Tastaturtest: alter leerer Mount → sichtbarer Diff-Fehler → Agent
  auswählen → richtiger Workspace → Repository-Inspektion wieder erfolgreich.
- Grenzen: View diff zeigt Änderungen gegen HEAD, keine bereits committierten
  Änderungen relativ zu main. Diese stehen in der Commit-Historie.
- Nächster Schritt: Nutzer aktualisiert Client/Backend und prüft aktuellen Worker.
- Git-Commit-ID: git log --format='%h %s' --grep='inspect Git in the selected agent workspace'.
- Vollständige Prüfung scripts/check.sh PASS: 157 pytest-Tests, Ruff/Format,
  Godot-Import, Zustands-, Headless- und Live-WebSocket-Tests. Eine bestehende
  Starlette/httpx-Abkündigungswarnung, keine Fehler.

## Bestehende Worktrees nach falscher Quellenwahl wieder anbinden — 2026-10-19

- Diagnose aus Nutzerumgebung: vorhandene Worker-Worktree-.git-Datei zeigt korrekt
  auf `/workspaces/project-1467da4f208c3c30b8b116-fd507a6f/.git/worktrees/...`;
  gemeinsames `.git` fehlte, weil der Starter zuvor den Desktop-Bind-Mount mit
  einer abweichenden ID `f7aeb5...` ausgewählt hatte.
- Starter hat nun optional `--workspace-id` zum bewussten Wiederanbinden des echten
  Host-Projekts an die ursprüngliche Container-ID. Identifier-Pfad validiert;
  Standardverhalten bleibt unverändert. Setup-Anleitung dokumentiert Reparatur.
- Test deckt Dry-run-Mountquelle und exaktes Ziel für die vorhandene ID ab und
  lehnt ungültige IDs ab. Projekt-Setup-Tests: 17 PASS.
- Dateien: scripts/setup-project.py, backend/tests/test_project_setup.py,
  docs/project-setup.md, PROGRESS.md.
- Nächster Schritt: vollständige `scripts/check.sh`, Commit und Push. Dann kann
  Nutzer das echte SimulationWorld-Repo unter vorhandener ID anbinden; bestehende
  Worker-Arbeitsverzeichnisse und Branches werden dadurch nicht gelöscht.
- Git-Commit-ID: git log --format='%h %s' --grep='restore existing worktree mounts'.
- Vollständige Prüfung: scripts/check.sh PASS — 159 pytest-Tests, Ruff/Format,
  Godot-Import, Zustands-, Headless- und Live-WebSocket-Tests.

## Projektverwaltung, Branch-Veröffentlichung und Recaps — 2026-10-19

- Starter erkennt dieselbe Git-Repository-`origin`-Adresse über unterschiedliche
  Host-/WSL-Pfade hinweg wieder. Lokal wird nur Hash→Workspace-ID gespeichert;
  `--workspace-id` bleibt die gezielte Reparatur für existierende Worktrees.
- Setup bietet Löschen des gewählten Projekts oder aller verwalteten Projekte mit
  Bestätigung. Laufende oder unsaubere Worktrees blockieren es. Quellrepository,
  Branches und Ausführungshistorie bleiben erhalten. Gemeinsame Worktree-Metadaten
  werden erst bereinigt, nachdem alle Worktrees des Projekts entfernt wurden.
- Erfolgreiche Läufe zeigen in Executions einen Recap plus Branch-/Commit-Nachweis.
  Der Controller committet `agent-changelogs/<agent-id>.md` und pusht ausschließlich
  auf den jeweiligen Worker-Branch. Der Integrationsagent führt beide Workerstände
  auf eigenem Branch zusammen und darf den gemeinsam geprüften Stand nach `main`
  promoten, wenn die Integration ausdrücklich aktiviert wurde.
- Setup wählt Integration und Veröffentlichung standardmäßig aus; der Backend-Start
  muss Remote-Pushes separat über `--publish-results` freigeben. Setup startet keine
  Modellaufgabe.
- Geändert: Starter und Tests, Management API/Execution/Git/Storage, Godot Setup-UI
  und Eingabetests, Projekt-Setup-Dokumentation.
- Verifikation: `scripts/check.sh` PASS — 163 pytest-Tests, Ruff/Format,
  Godot-Import, Zustands- und Headless-Tests sowie Live-WebSocket-/GUI-Integration.
  Zusätzlich 16 fokussierte Team-Integration-, Worker-Publish- und
  Mehr-Worktree-Löschtests PASS. Eine bestehende Starlette/httpx-Abkündigungswarnung.
- Git-Commit-ID: wird über `git log --grep='reuse selected repositories and publish agent recaps'`
  nachverfolgt; Commit und Push erfolgen nach dieser Prüfung.
- Offen: keine bekannte Implementierungslücke in diesem Meilenstein. Grafische
  Sichtprüfung auf dem Windows-/WSL-Zielhost bleibt erforderlich.

## Löschansicht aktualisiert zugewiesene Workspaces — 2026-10-20

- Befund: Nach bestätigter Projektlöschung wurden Backend-Workspace-Zuordnungen
  und Worktree-Ordner entfernt, aber der Godot-Client behielt die alten
  Workspace-Datensätze im lokalen Cache. Dadurch wirkten zugewiesene Workspaces
  weiterhin vorhanden.
- Behoben: Erfolgsantwort entfernt jetzt Projekt, Teamagenten und deren
  zugewiesene Worker-Workspaces aus dem UI-Cache und aktualisiert die Ansichten.
  Der Workspace des ausgewählten Quellrepositories bleibt sichtbar.
- Tests: Godot-Setup-GUI bestätigt vor/nachher die Workspace-Zahlen und den
  erhaltenen Quellworkspace; Backend-Löschtest prüft die persistierten Workspace-
  Datensätze. Gezielter nativer GUI-Test PASS.
- Vollständige `scripts/check.sh` PASS: 163 pytest-Tests, Ruff/Format, Godot-Import,
  Zustands-/Headless-Test und Live-WebSocket-Smoke. Godot-Setup-GUI-Regression
  einschließlich Worker-Workspace-Löschung PASS.
- GitHub-CI-Prüfung: `main` zeigt auf `a0954cd`; dessen kompletter lokaler Check
  besteht mit 113 Tests plus Godot- und WebSocket-Tests. GitHub meldet für Actions
  Run #17 nur den Sammelschritt `Unit, integration and Godot checks` als fehlgeschlagen;
  öffentliche Annotations enthalten keine Testausgabe. Die Warnungen zu Node 20
  und Ubuntu-Migration erklären den Fehler nicht. Konkreter Runner-Unterschied ist
  ohne authentifizierte Job-Logs nicht belegt.
- CI-Diagnostik: `scripts/check.sh` kann nun einzelne Stufen ausführen; GitHub
  Actions zeigt Lint, pytest, Godot-Import, Zustands-/Headless-Tests und WebSocket-
  Smoke getrennt an. Der nächste Lauf lokalisiert den GitHub-spezifischen Fehler.
- Der GitHub-Lauf für `94de70b` ist ebenfalls im alten Sammelschritt fehlgeschlagen;
  damit ist es kein Fehler der Workspace-Cache-Korrektur. Die neue aufgeteilte
  Workflow-Konfiguration läuft erst mit dem nächsten Commit.
- Geprüft: `scripts/check.sh` nach der Aufteilung vollständig PASS — 163 pytest,
  Ruff/Format, Godot-Import, Zustands-/Headless-Test und Live-WebSocket-Smoke.
- Git-Commit-ID: wird über `git log --grep='remove deleted worker workspaces from setup UI'`
  nachverfolgt.

## GitHub-pytest-Fehler weiter eingegrenzt — 2026-10-20

- Der Diagnose-Lauf `39489840780` besteht Ruff, scheitert aber im zusammengefassten
  Backend-pytest-Schritt; die folgenden Godot-Prüfungen werden übersprungen.
- CI zerlegt pytest nun in vier separat benannte Gruppen (Runtime, Verwaltung,
  Ausführung/Git/Team und GUI), damit GitHub den fehlschlagenden Bereich anzeigt.
- Lokal vollständig grün: 163 pytest-Tests, Ruff/Format, Godot-Import,
  Zustands-/Headless-Tests und Live-WebSocket-Smoke.
- Die Gruppen decken gemeinsam alle pytest-Dateien unter `backend/tests` ab.
- Offen: nächster GitHub-Lauf nötig, um festzustellen, welche Testdatei abweicht;
  anonyme Actions-Ansicht liefert weiterhin keine pytest-Ausgabe.
- Der erste aufgeteilte GitHub-Lauf zeigte `Backend core and runtime tests` als
  fehlerhaft. Diese fünf Dateien laufen jetzt in getrennten CI-Schritten.
- Der nächste Lauf lokalisierte es auf `test_sandbox_diagnostics.py`: dessen
  echter Bubblewrap-Test verlangte zwingend verfügbare User-Namespaces. Hosted
  Runner können diese Kernel-Fähigkeit sperren; korrekt ist dort ein
  klassifiziertes `namespace_denied` bei geschlossenem Agentstart. Der Test
  prüft nun sowohl echte Bereitschaft als auch diesen sicheren Fehlerpfad.
- Der aktuelle CI-Lauf besteht Sandbox-Diagnose, Backend, Codex, Reconnect,
  Rollen/Messaging, Sandbox und Ruff; Fehler liegt nun in der Management-Gruppe.
  Auch diese fünf Dateien erhalten einzelne CI-Schritte zur exakten Eingrenzung.
- Erneute vollständige Prüfung vor diesem Commit: 163 pytest PASS, Ruff/Format,
  Godot-Import, Zustands-/Headless-Tests und Live-WebSocket-Smoke PASS.
- Erneuter Gesamtcheck nach dem weiteren CI-Split ebenfalls PASS: 163 pytest,
  Ruff/Format, Godot-Import, Zustands-/Headless-Tests und WebSocket-Smoke.
- CI-Testfehler geben nun ausschließlich Test-ID und Exception-Typ als
  GitHub-Annotation und Job-Zusammenfassung aus; sensible Tracebacks bleiben im
  privaten Runner-Log. Vollcheck mit dieser Änderung erneut PASS (163 pytest und
  sämtliche Ruff-/Godot-/WebSocket-Prüfungen).
- Die Annotation identifiziert nun auch den Quellcode-Zeilenort des Testfehlers,
  ohne Assertion-Werte oder Traceback-Inhalte offenzulegen.
- Nach der Korrektur: gezielte Sandbox-Diagnose 10/10 PASS; erneuter Gesamtcheck
  163 pytest PASS, Ruff/Format, Godot-Import, Zustands-/Headless-Tests und
  Live-WebSocket-Smoke PASS.
- Commit: `git log --format='%h %s' -1` (Push nach `feat/virtual-agent-cafe-mvp`).
- Dateien: `.github/workflows/ci.yml`, `scripts/check.sh`, `PROGRESS.md`.
- Git-Commit-ID: nach erfolgreicher CI-Workflow-Prüfung eintragen.

## CI-Sandbox als Voraussetzung prüfen — 2026-10-20

- Korrektur zur bisherigen Diagnose: Der genaue Fehler auf `main` ist noch nicht
  aus Logs bestätigt; Dateinamen neuer Feature-Tests belegen keinen Fehlerort auf
  dem älteren main-Stand. Die Lockerung des Sandbox-Diagnosetests verdeckte eine
  notwendige Voraussetzung und wurde zurückgenommen.
- CI prüft jetzt vor allen Tests echte Namespace-Isolation. Bei nachgewiesenem
  `namespace_denied` und aktiver Ubuntu-AppArmor-Userns-Sperre wird ausschließlich
  für `/usr/bin/bwrap` ein Profil auf dem temporären Runner geladen. Anschließend
  muss die echte Sandbox-Probe bestehen. Keine Änderungen an Produktionshosts.
- Grundlage: Ubuntu-Dokumentation zu AppArmor und unprivilegierten User-Namespaces.
- Pytest-Annotationen enthalten zusätzlich den Testdatei-Zeilenort, keine Werte.
- Validierung und GitHub-Ergebnis werden nach Abschluss ergänzt.
- Lokale Validierung: `scripts/check.sh` vollständig PASS, 163 pytest, Ruff,
  Godot-Import/States/Headless und WebSocket-Smoke. Shell-Syntaxprüfung PASS.
- Commit auffindbar mit `git log --grep='prepare real namespace isolation on CI runners'`.
- GitHub Run 39494719463 bestätigt `Initial sandbox result: namespace_denied`.
  Mit dem Bwrap-Profil bestehen anschließend Sandbox-, Agentlösch-, Definitions-,
  Projektlösch-, Projektdokument- und Setup-Tests. Der ursprüngliche Hostfehler ist
  damit für diesen Runner nachgewiesen.
- Noch drei Team-Integrationstests scheitern an gemeinsamer pytest-Validierung.
  `validation.py` verwendet `sys.executable`; setup-python legt es außerhalb der
  Sandbox-Freigaben in `/opt/hostedtoolcache` ab. CI verwendet jetzt wie Docker
  `/opt/venv` mit System-Python und festem Ubuntu 24.04 (Python 3.12).
- Vor Commit zur Python-Laufzeit: vollständiger `scripts/check.sh` PASS, 163 pytest,
  Ruff/Format, Godot-Import/States/Headless und WebSocket-Smoke.
- Vorheriger CI-Fix: e0280be; Python-Fix über Commit-Betreff
  `align CI Python with the sandbox runtime` nachvollziehbar.

## CI vollständig grün — bestätigtes Ergebnis

- Getesteter Code-Commit: `00f7bec` (enthält Sandbox-Fix `e0280be`).
- GitHub Actions: https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/39495521850
  vollständig SUCCESS. Backend-, Git-/Team-, native GUI-, Godot-Import/States/
  Headless-, WebSocket-, Shader-/Management-Rendering-, echte GUI-Eingabe-,
  Compose- und Container-Build/Health-Prüfungen erfolgreich.
- Nachgewiesene Runner-Ursache: AppArmor verweigerte zunächst User-Namespaces
  (`namespace_denied`). Gezieltes Profil für Bubblewrap behebt die Git-/Workspace-
  Tests. Mit Python in `/opt/venv` bestehen auch alle gemeinsamen Teamtests.
- Der ältere `main` enthält diese CI-Korrekturen noch nicht; kein automatischer
  Merge erfolgt. Sein damaliger einzelner Traceback ist weiterhin nicht öffentlich
  abrufbar. Die fehlerhaften CI-Voraussetzungen sind auf dem Feature-Branch behoben.
- Dieser Nachtrag ändert nur Dokumentation; Code identisch zum vollständig grünen
  GitHub-Lauf und zur zuletzt bestandenen lokalen Gesamtsuite mit 163 Tests.

## Automatische lokale Management-Verbindung — 2026-10-21

- Starter speichert die Verbindung atomar mit Modus 0600 unter
  `.runtime/setup/godot-connection.json`, auch bei `--no-godot` und wenn Godot
  nicht automatisch gefunden wird. Keine Token-Ausgabe; bestehende Git-/Docker-
  Ausschlüsse für `.runtime` gelten. Token bleibt außerhalb der Agent-Workspaces.
- Godot lädt die Verbindung bei manuellem Neustart und über Connect / Refresh.
  Das Tokenfeld ist standardmäßig verborgen; Connection settings öffnet es für
  Sonderfälle. Gespeicherte Tokens gelten ausschließlich für die gespeicherte
  Backend-URL. Explizite Umgebungsvariablen haben Vorrang. Backend-Auth bleibt aktiv.
- Dateien: scripts/setup-project.py; game/scripts/local_connection.gd (+ UID),
  management.gd; Launcher-/Godot-/GUI-Integrationstests; Setup-/Management-Anleitungen.
- Tests: `scripts/check.sh` vollständig PASS, 165 pytest, Ruff/Format, Godot-Import,
  Zustands-/Headless- und WebSocket-Smoke. Neuer nativer GUI-Integrationstest
  verwaltet Agenten mit gespeicherter Datei ohne Token-Umgebungsvariable. Tests
  prüfen 0600, Backend-Bindung und beschädigte JSON-Dateien.
- Einrichtung einmal erneut starten, danach Godot neu öffnen. Exportierte Clients
  können VAC_CONNECTION_FILE verwenden. Keine Änderung an main.
- Commit-ID über `git log --grep='connect Godot automatically after project setup'`.

## Workspace- und Task-Löschung — 2026-10-21

- Agents-Seite ergänzt: ausgewählten Workspace-Eintrag entfernen und Markdown-Task
  löschen; beide Aktionen verlangen Bestätigung. Workspaces werden aus der
  Registrierung genommen, ihre Ordner, Dateien und Git-Daten bleiben erhalten.
  Tasks werden dauerhaft gelöscht; aktive Zuordnungen verhindern die Aktion.
- Backend-DELETE-Endpunkte verlangen `confirmed: true`, prüfen Pfade, persistente
  Agentenzuordnungen und Projektquellen unter derselben Management-Sperre.
- GUI setzt eine gelöschte Auswahl auf die gespeicherte Agentenkonfiguration zurück.
  Zusätzlich wird die Agentenliste nach Agentenlöschung lokal aktualisiert; zuvor
  wurde die Serverantwort bestätigt, ohne die lokale Liste zu entfernen.
- Geändert: `management/api.py`, `execution.py`, `files.py`, API-/GUI-Tests,
  `game/scripts/management.gd`, `docs/agent-management.md`.
- Tests: `scripts/check.sh` vollständig PASS; 168 pytest bestanden, Ruff und Format
  grün, Godot-Import/Zustände/Headless grün, Live-WebSocket-Smoke grün.
  Vorhandene Starlette/httpx-Deprecation-Warnung bleibt bestehen.
- Commit-ID: nachfolgender PROGRESS-Eintrag.
- Offen: Workspace-Ordner werden absichtlich nicht physisch gelöscht, damit
  Projektdateien und Git-Verläufe nicht versehentlich verloren gehen.
