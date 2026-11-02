# VirtualAgentCafe

VirtualAgentCafe zeigt echte Codex-Agenten als Charaktere in einem Godot-Café.
Backend- und Frontend-Agent arbeiten in getrennten Git-Worktrees an deinem Projekt.
Ein Integrationsagent führt ihre Ergebnisse zusammen und prüft sie vor der
optionalen Veröffentlichung auf `main`. Animationen folgen tatsächlichen
Laufzeitereignissen wie Programmieren, Testen, Warten und Abschluss.

## Voraussetzungen

Für den normalen Betrieb verwendest du **das Python-Setup-Skript und Godot**.
Das Skript baut und startet das Backend mit Docker Compose; Python-Pakete, Codex CLI,
Git und Testwerkzeuge für die Agenten werden im Container installiert.

| Voraussetzung auf deinem Rechner | Wofür? |
| --- | --- |
| Linux oder Windows mit WSL2 | Das Setup-Skript läuft auf dem Linux-/WSL-Host. |
| Python **3.10+** | Führt `scripts/setup-project.py` aus; keine zusätzlichen Python-Pakete nötig. |
| Docker mit Compose V2 und Unterstützung für `up --wait` | Baut und betreibt das Backend. Unter Windows Docker Desktop starten und die WSL-Integration aktivieren. |
| Godot **4.4.1 Standard** | Öffnet die Café-Oberfläche. Unter Windows kann die Windows-Version verwendet werden. |
| Git und ein VirtualAgentCafe-Checkout | Zum Herunterladen und Aktualisieren dieser Anwendung. |
| Ein separates Projekt mit echtem `.git`-Verzeichnis und mindestens einem Commit | Das ist der Ordner, den die Agenten bearbeiten sollen; kein bestehender Worktree und nicht VirtualAgentCafe selbst. |
| Codex-Zugang | Der Starter öffnet bei fehlender Anmeldung den Login im Container. Die Agenten verwenden diesen gemeinsamen Zugang; Modellnutzung kann Kosten verursachen. |
| Git-Remote und SSH-Zugang mit Schreibrechten, wenn Ergebnisse gepusht werden sollen | Im Zielprojekt muss `origin` auf dein Repository zeigen. Ein geladener SSH-Agent und geprüfte `~/.ssh/known_hosts` werden vom Starter eingebunden. |

Für die Ordnerauswahl nutzt WSL Windows PowerShell. Unter Linux ist Python-Tk mit
grafischer Sitzung optional; ohne Dialog fragt das Skript nach dem Pfad.
Die Agenten benötigen funktionierende Linux-Namespaces/Bubblewrap. Der Starter
prüft das vor dem Start. Für lokale Umgebungen, die den zusätzlichen Containerzugriff
benötigen, gibt es den ausdrücklich gewählten Schalter `--privileged`.

## Getting started

### 1. VirtualAgentCafe herunterladen

Im Linux-/WSL-Terminal:

```bash
git clone https://github.com/St3fanTh/VirtualAgentCafe.git
cd VirtualAgentCafe
```

Bei einem vorhandenen Checkout zuerst eigene Änderungen sichern, dann auf `main`
wechseln und aktualisieren:

```bash
git switch main
git pull --ff-only origin main
```

### 2. Dein Projekt vorbereiten

Wähle später den Hauptordner deines eigenen Git-Projekts, beispielsweise
`/mnt/f/Workspace/SimulationWorld`. Dort gehören auch diese Dateien hin:

- **AGENTS.md:** gemeinsame Regeln, Architekturvorgaben und Einschränkungen.
- **PLANNING.md:** Ziele, nächste Aufgaben und prüfbare Abnahmekriterien.

Vorhandene Dateien können im Assistenten geladen und bearbeitet werden. Fehlende
Dateien erhalten Vorlagen. Auch `agents.md` und `planning.md` werden erkannt.
Projekt-Markdown darf jeweils bis zu **64 KiB UTF-8** groß sein; eine Überschrift
ist nicht vorgeschrieben. Committe den gewünschten Ausgangsstand: Neue Worktrees
beginnen bei `HEAD`, uncommittete Dateien werden nicht automatisch mitgenommen.

Für Veröffentlichungen: Lade deinen vorhandenen SSH-Schlüssel in den SSH-Agenten
und prüfe den Git-Zugang auf dem Host. Der öffentliche Schlüssel muss beim
Git-Anbieter hinterlegt sein. Private Schlüssel gehören weder in die GUI noch
in das Repository. Details: [Git-Zugang und Setup](docs/project-setup.md).

### 3. Setup starten und Projektordner auswählen

Im **VirtualAgentCafe-Verzeichnis auf dem Host**, nicht im Container:

```bash
python3 scripts/setup-project.py --publish-results
```

Der Ordnerdialog öffnet sich. Wähle dein Projekt mit `.git`. Der Starter:

1. Bindet genau diesen Projektordner ein und verwendet dessen Git-Repository.
2. Baut/startet das Backend und prüft die Sandbox.
3. Öffnet die Codex-Anmeldung, falls nötig, und speichert sie im Container-Volume.
4. Speichert die lokale Verbindung für Godot, ohne dass du einen Token eintippen musst.
5. Startet Godot, wenn `godot` oder `godot4` im PATH gefunden wird.

`--publish-results` erlaubt Remote-Git für spätere Veröffentlichungen. Das Setup
allein startet noch keine Agenten und führt keine Pushes oder Merges aus.
Ohne diesen Schalter ist lokales Arbeiten möglich; der automatische Ablauf bis
Remote-`main` benötigt die Remote-Freigabe.

Für Windows-Godot kannst du den Pfad angeben:

```bash
python3 scripts/setup-project.py --publish-results \
  --godot '/mnt/c/Tools/Godot/Godot_v4.4.1-stable_win64.exe'
```

Falls deine lokale Umgebung den Namespace-Override benötigt, ergänze `--privileged`:

```bash
python3 scripts/setup-project.py --publish-results --privileged
```

Alternativ öffnest du in Godot **`game/project.godot`** aus diesem Checkout und
startest mit **F5**. Wenn der Starter Godot direkt öffnet, ist F5 nicht nötig.
Mit `--no-godot` startet nur das Backend; mit `--login` öffnest du die Anmeldung erneut.

### 4. Team im Café einrichten

1. **Manage agents → Setup project** öffnen und das eingebundene Projekt wählen.
2. **Load project documents** klicken. `AGENTS.md` und `PLANNING.md` prüfen; über
   **Import Markdown file** lassen sich weitere lokale Inhalte auswählen.
   **Save project document** speichert Änderungen im Projektordner.
3. Das Ziel beschreiben oder die geladene Planung verwenden. **Check project**
   ausführen und angezeigte **FIX**-Hinweise beheben.
4. Für den vollständigen Ablauf **Push successful results to each agent's own Git branch** und
   **Integrate + requirements tests + promote green result to main** aktivieren.
5. **Create backend + frontend team** klicken. Mit Integration entsteht zusätzlich
   der Integrations-/Testagent. Die Erstellung allein startet keine Modellaufträge.
6. Unter **Agents** bei Bedarf pro Agent das **Model** wählen und
   **Save configuration** klicken. Danach Backend und Frontend jeweils mit
   **Start agent** starten.

## Der Arbeitsablauf

### Entwickeln → integrieren → testen → veröffentlichen

1. **Backend und Frontend arbeiten parallel.** Jeder Agent hat einen eigenen
   Worktree, Aufgaben, Rollen und einen eigenen Branch. Fortschritt und echte
   CLI-Testereignisse erscheinen im Café und in den Live Logs.
2. **Erfolgreiche Worker veröffentlichen ihre Ergebnisse auf ihren Agenten-Branches.**
   `Done`/`Completed` bedeutet noch nicht, dass das Gesamtprojekt auf `main` steht.
   Prüfe zusätzlich den Veröffentlichungsstatus **Pushed**.
3. **Der Integrator startet automatisch**, wenn die Team-Automatik eingeschaltet
   ist und beide erforderlichen Worker-Ergebnisse erfolgreich veröffentlicht sind.
   Er führt deren konkrete Commits auf einem Integrationsbranch zusammen und
   erstellt bzw. aktualisiert gemeinsame Requirements-Tests.
4. **Der Controller prüft den eingereichten Stand erneut.** Nur nach erfolgreicher
   gemeinsamer Validierung wird der geprüfte Commit ohne Force-Push nach Remote-`main`
   übernommen. Fehlschläge verhindern die Promotion; grüne Tests ersetzen trotzdem
   nicht deinen eigenen Produkttest.
5. **Du prüfst das Ergebnis.** Unter **Executions** findest du Berichte, Tests und
   Changelogs; Git-Ansichten zeigen Branch, Commits und Diffs. Agenten-Recaps liegen
   auch unter `agent-changelogs/` im Ergebnisrepository. Aktualisiere deinen lokalen
   Zielprojekt-Checkout mit `git pull --ff-only origin main`, bevor du ihn testest.
   Der Controller überschreibt deinen lokalen Quell-Checkout nicht automatisch.

Die vollständigen Regeln stehen unter [automatische Integration](docs/automatic-integration.md).

### Wenn ein Agent Hilfe braucht

Integrationsfehler werden innerhalb eines begrenzten Budgets automatisch erneut
bearbeitet. Bei wiederholtem Fehler oder ausgeschöpftem Budget pausiert das Team
als **NEEDS_INPUT**. Unter **Manage agents → Agent chat** gibt es zwei getrennte Wege:

- **Ask question:** etwa „Wo ist das Startskript?“ Der Agent liest das Projekt
  schreibgeschützt und antwortet. Es startet keine Entwicklung oder Integration;
  der bisherige Arbeitsstatus bleibt erhalten.
- **Send instruction & continue:** etwa „Behebe diesen Test anhand dieser Vorgabe“.
  Das setzt die Arbeit fort und kann anschließend die Team-Integration auslösen.
  Während eines laufenden Auftrags gespeicherte Anweisungen gelten für den nächsten Versuch.

Die Antwort auf eine Frage erscheint im Chat. Für aktive Arbeit stehen zusätzlich
Live Logs und Ausführungsberichte bereit. **Retry team integration** stößt einen
weiteren Integrationsversuch an; bei einem fachlichen Blocker zuerst eine konkrete
Arbeitsanweisung geben. Fragen und Arbeitsanweisungen verwenden das konfigurierte Modell.

### Nächste Runde nach deinem Test

Agenten und Worktrees behalten; kein neues Team und kein erneutes Setup nötig:

1. Im **Setup project** das vorhandene Projekt auswählen und **Load project documents** klicken.
2. Unter **NEXT ITERATION** neue Anforderungen und Abnahmekriterien eintragen.
3. **Start next iteration** klicken.

Der Controller übernimmt den aktuellen Remote-`main` in die sauberen Worker-Branches,
ergänzt die Planung und startet beide Worker für diese Runde. Danach folgen wieder
Integration, gemeinsame Tests und die freigegebene Main-Veröffentlichung.
Bloßes Editieren von `PLANNING.md` startet keine Runde. Bei Änderungen auf GitHub
zuerst den lokalen Projektordner aktualisieren und die Dokumente neu laden.

## Neustart, Verbindung und Fehlerbehebung

- **Nach einem VirtualAgentCafe-Update:** `git pull --ff-only origin main` im
  VirtualAgentCafe-Checkout, dann den Starter mit denselben benötigten Optionen
  erneut ausführen und Godot neu öffnen. Den gleichen echten Projektordner wählen.
- **Connection settings:** manuelle Backend-Adresse/Anmeldung für Sonderfälle.
  Beim normalen Starter-Ablauf werden die Einstellungen automatisch geladen;
  **Connect / Refresh** lädt sie erneut. Die API bleibt durch einen lokal
  gespeicherten Token geschützt.
- **No visible git project:** Den Starter auf dem Host erneut ausführen und den
  Hauptordner mit `.git` auswählen. **Find projects** durchsucht nur freigegebene
  Mounts und kann keine beliebigen Hostordner einbinden.
- **Namespace sandbox unavailable:** Die Hinweise des Starters befolgen; für die
  lokale Umgebung gegebenenfalls `--privileged` verwenden. Isolation bleibt erforderlich.
- **Codex login fehlt:** Starter mit `--login` erneut ausführen.
- **Git push failed:** Remote und SSH-Zugang müssen auch im Backend verfügbar sein.
  Den Starter im Terminal mit geladenem SSH-Agenten und `known_hosts` ausführen.
- **Port erreichbar, aber keine Café-Seite:** Die Oberfläche ist die native
  Godot-Anwendung. `http://127.0.0.1:8000/health` ist nur ein Backend-Healthcheck.
- **Daten behalten:** Konfigurationen, Historie und Worktrees sind persistent.
  `.runtime` und Docker-Volumes nicht löschen, wenn du weiterarbeiten möchtest.

Das Backend ist lokal über `127.0.0.1:8000` erreichbar. Ein Backend-Prozess betreibt
die Verwaltung; Browser-Exports werden nicht unterstützt. Private Anmeldedaten,
Tokens und `.runtime` gehören nicht ins Git-Repository.

## Entwicklung und Tests an VirtualAgentCafe

Für die normale Nutzung ist keine lokale Backend-Installation nötig. Wer am
VirtualAgentCafe-Code arbeitet, benötigt zusätzlich Python **3.12+**, die Pakete aus
`backend/requirements.lock`, Linux-Godot und Bubblewrap mit funktionierenden Namespaces.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.lock
python -m pip install --no-deps -e backend
scripts/check.sh
```

Die Prüfung umfasst Ruff, pytest einschließlich API-, Git-, Sandbox- und GUI-Tests,
Godot-Import, Zustandsprüfungen, Headless-Start und einen Live-WebSocket-Smoke-Test.
GitHub Actions prüft zusätzlich gerenderte Oberflächen, Compose und den Containerstart.
Normale Tests verwenden deterministische Laufzeit-Fixtures und benötigen keinen
bezahlten Modellaufruf. Ein echter Codex-Smoke-Test ist separat über
`scripts/codex-smoke.sh` möglich. `scripts/demo.sh demo` startet eine ausdrücklich
als simuliert markierte Demo ohne Codex-Zugang.

## Weitere Dokumentation

- [Ausführlicher Setup-Assistent](docs/project-setup.md)
- [Agentenverwaltung, Modelle und Chat](docs/agent-management.md)
- [Automatische Integration und Requirements-Tests](docs/automatic-integration.md)
- [Controller-Prüfungen, Fehlerdiagnose und Abnahmestatus](docs/controller-validation.md)
- [Container-Sandbox](docs/container-sandbox.md)
- [Architektur](docs/architecture.md) und [Event-Protokoll](docs/event-schema.md)
- [Grafik und 4K-Darstellung](docs/graphics.md)
- [Änderungen und Testnachweise](PROGRESS.md)
