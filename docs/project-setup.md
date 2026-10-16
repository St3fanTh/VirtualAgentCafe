# Einrichtungsassistent für eigene Projekte

Der lokale Starter wählt einen bestehenden Git-Projektordner aus, startet das
Compose-Backend und öffnet Godot direkt im Assistenten. Dort werden Codex-Anmeldung,
Namespace-Sandbox und Git geprüft. Aus deiner Zielbeschreibung entstehen zwei
Agenten mit Markdown-Aufgaben/Rollen, eigenen Git-Worktrees und eigenen Branches.
Die bestehende Architektur und Verwaltung bleiben erhalten.

![Einrichtungsassistent mit Beispieldaten](images/setup-preview.png)

## Start auf dem Linux-/WSL-Docker-Host

Voraussetzungen: Python 3.10+, Docker Compose mit `up --wait`, Godot 4.4.1 und ein
bestehendes lokales Hauptrepository mit mindestens einem Commit. Führe den Starter
im VirtualAgentCafe-Checkout auf dem Host aus, nicht im Backend-Container:

```bash
python3 scripts/setup-project.py
```

Ein Ordnerdialog öffnet sich, sofern Python-Tk und eine grafische Sitzung verfügbar
sind. Andernfalls fragt der Starter den Projektpfad im Terminal ab. Du kannst ihn
auch direkt angeben:

```bash
python3 scripts/setup-project.py --project /home/du/projekte/meine-app
```

Für die bisher verwendete lokale Entwicklungsumgebung, die den Privileged-Override
benötigt:

```bash
python3 scripts/setup-project.py --privileged
```

Der Starter startet das Backend im Codex-Modus und wartet auf den Healthcheck.
Fehlt die Codex-Anmeldung, öffnet er `codex login` im Container und setzt danach fort.
Mit `--login` kannst du den Anmeldevorgang ausdrücklich erneut öffnen. Die Anmeldung
bleibt im vorhandenen `codex_home`-Volume. Beide Agenten verwenden diesen Zugang;
getrennte Accounts pro Agent sind noch nicht vorgesehen.

Godot wird über `godot`/`godot4` im PATH erkannt oder explizit gewählt:

```bash
python3 scripts/setup-project.py --privileged \
  --godot '/mnt/c/Tools/Godot/Godot_v4.4.1-stable_win64.exe'
```

Bei Windows-Godot aus WSL übersetzt der Starter den Spielpfad mit `wslpath` und
übergibt Verbindungseinstellungen über `WSLENV`. Er startet direkt das Spiel;
F5 ist dabei nicht nötig. Der Managementtoken wird nur im Prozessspeicher an Godot
übergeben und weder angezeigt noch in die generierten Dateien geschrieben.

`--no-godot` startet nur das Backend. Bei manuellem Godot-Start gilt weiter die
[Token-Verbindung aus der Verwaltungsanleitung](agent-management.md).

## Im Assistenten

1. **Setup project** öffnet die Seite. Beim Start über den Starter ist das gewählte
   Projekt bereits ausgewählt. Angezeigt werden nur freigegebene Hauptrepositories.
2. Beschreibe das Ziel, die Aufteilung und möglichst den gemeinsamen API-Vertrag.
3. **Check project** prüft Sandbox, gespeicherte Codex-Anmeldung, Codex-Modus und
   initialen Commit. Fehler erscheinen mit Handlungshinweisen. Die Prüfung führt
   keinen Modellauftrag aus und bestätigt keine serverseitige Modellverfügbarkeit.
4. **Create backend + frontend team** erstellt beide Worktrees und Konfigurationen.
   Agenten heißen `PROJEKT-backend` und `PROJEKT-frontend`; ihre Branches liegen
   unter `agent/AGENT/implementation`. Aufgaben und Rollen sind weiterhin Markdown.
5. Unter **Markdown** die Aufgaben prüfen/anpassen. Unter **Agents** jeden Agenten
   auswählen und **Start agent** klicken. Die Einrichtung allein startet keine
   kostenpflichtigen Modellaufgaben.
6. Ergebnisse, Tests und Diffs prüfen. Annahme und späterer Merge erfolgen bewusst;
   der Assistent pusht oder merged nicht.

Uncommittete Änderungen bleiben im Quellrepository. Die Agentenworktrees beginnen
bei dessen HEAD; der Assistent zeigt diesen Unterschied an und erstellt selbst
keinen initialen Commit. Für einen neuen Ausgangsstand zuerst deine gewünschten
Änderungen selbst prüfen und committen.

## SSH und Remote-Prüfung

Ist auf dem Host `SSH_AUTH_SOCK` ein erreichbarer Socket und existiert
`~/.ssh/known_hosts`, bindet der Starter beides gezielt für den Git-Dienst ein.
Private Schlüssel werden nicht kopiert oder eingebunden. Codex-Worker erhalten den
SSH-Socket nicht. Bekannte Server müssen bereits mit überprüften Host-Schlüsseln
in `known_hosts` stehen; die Prüfung wird nie abgeschaltet.

Eine Remote-Prüfung ist optional. Aktiviere sie beim Start und anschließend über
das Kontrollkästchen im Assistenten:

```bash
python3 scripts/setup-project.py --privileged --remote-checks
```

Diese Prüfung verwendet ausschließlich `git ls-remote` gegen ein unterstütztes,
zugangsdatenfreies `origin` und prüft lesenden Zugriff. Sie erzeugt keinen
Testbranch und bestätigt keine Push-Berechtigung. Fehler weisen auf SSH-Agent,
Host-Schlüssel oder Repository-Berechtigungen hin. Die neuen Agenten erhalten
weiterhin keine Push-/Pull-/Fetch-Freigaben.

## Dateien, Persistenz und Grenzen

- Der generierte Compose-Override liegt ignoriert unter
  `.runtime/setup/project.compose.json`. Nur der gewählte externe Projektordner
  wird zusätzlich eingebunden; kein beliebiger Hostpfad ist über die API wählbar.
- Projekt-IDs enthalten einen kurzen Pfad-Hash, damit gleichnamige Ordner nicht
  versehentlich dasselbe Team verwenden. Der Starter unterstützt ein ausgewähltes
  externes Quellprojekt pro Backend-Start. Starte ihn zum Wiederöffnen erneut mit
  demselben Ordner; beim Projektwechsel bleiben alte Arbeitsstände erhalten.
- Compose erstellt das Backend bei geänderter Konfiguration/Image neu. Beende
  laufende Aufgaben vor einem Projektwechsel oder einem solchen Neustart.
- Agentenworktrees liegen im persistenten `agent_workspaces`-Volume. Die Git-
  Verwaltungsdaten liegen auch im `.git` des freigegebenen Quellprojekts. Diese
  Worktrees gehören zur Containerumgebung; Ergebnisse sind dort über Verwaltung,
  Git-Diffs und bei Bedarf `docker compose cp` erreichbar.
- Ein erneuter Teamerstellungsversuch erhält vorhandene Aufgaben/Konfigurationen.
  Unterbrochene Einrichtungen werden mit der ursprünglichen Zielbeschreibung
  fortgesetzt. Bestehende fremde Dateien werden nicht überschrieben.
- Native Windows-/macOS-Launcher ohne Linux/WSL-Host, SSH-Agent-Brücken für Windows
  ohne WSL-Socket und Git-Submodule sind kein Bestandteil dieses Assistenten.
- Docker-Start, nativer Tk-Dialog und Windows-Übergabe benötigen einen Test auf dem
  Zielhost. Hier sind Launcher-Verträge automatisiert getestet; der Entwicklungs-
  container stellt keinen Docker-Daemon für einen vollständigen Hostlauf bereit.

Mount-Plan ohne Start/Änderungen anzeigen:

```bash
python3 scripts/setup-project.py --project /pfad/zum/projekt --dry-run
```

## API und Tests

Alle Routen benötigen den vorhandenen Managementtoken:

- `GET /management/setup`: freigegebene Hauptrepositories auflisten.
- `POST /management/setup/check`: `{ "project": "ID", "check_remote": false }`.
- `POST /management/setup/team`: `{ "project": "ID", "objective": "Ziel …" }`.

`scripts/check.sh` prüft Backend, Git-Worktrees, fehlende Voraussetzungen,
Wiederaufnahme, Konflikte, Pfad-/API-Schutz, Launcher-Mounts und Tokenbehandlung.
`game/tests/test_setup_input.gd` bedient den echten Assistenten mit Maus-/Tastatur-
Ereignissen gegen einen separaten Testserver. Nur der Codex-Anmeldestatus wird im
Fixture ersetzt; Git und Namespace-Prüfung laufen tatsächlich. Kein bezahlter
Modellaufruf und kein externer Git-Dienst ist für diese Tests nötig.
