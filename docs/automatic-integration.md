# Automatische Integration und gemeinsame Requirements-Tests

Der Ablauf benötigt keine manuelle Aufgabenannahme in **Executions**:

```text
Backend commit + push ─┐
                      ├─ Integrations-Feature-Branch ─ Requirements-Tests ─ main
Frontend commit + push┘
```

## Aktivieren

```bash
python3 scripts/setup-project.py --publish-results --privileged
```

`--privileged` nur verwenden, wenn deine lokale Containerumgebung es für die
Namespace-Isolation benötigt. Im Setup das bestehende Projekt prüfen, dann
**Integrate + requirements tests + promote green result to main** aktivieren und
**Create backend + frontend team** klicken. Das schaltet auch die Worker-Pushes
frei. Bestehende Aufgaben und Worktrees bleiben erhalten. Anschließend Backend und
Frontend unter **Agents** starten. Der zusätzliche **Integration & Tests**-Worker
startet automatisch, sobald beide aktuellen Aufgaben erfolgreich gepusht sind.

Git-Remote/SSH-Agent/known_hosts werden wie bisher vom Starter übernommen. Das
Remote muss einen `main` mit gemeinsamem Git-Verlauf besitzen. Benötigt werden
Schreibrechte für die Agenten-Branches und für `main`. Eine serverseitige
Branch-Schutzregel kann den direkten Main-Push ablehnen; sie wird nicht umgangen.

## Was automatisch passiert

1. Der Controller wartet auf erfolgreiche Pushes beider Worker und prüft Aufgaben-,
   Rollen- und Projekt-Snapshots. Fehlgeschlagene oder veraltete Läufe reichen nicht.
2. Der zusätzliche isolierte Worktree nutzt
   `agent/<projekt-id>-integration/validation`. Er übernimmt den aktuellen Remote-
   Main-Commit und die genauen veröffentlichten Worker-Commits mit normalen Merges.
3. Der Integrationsworker erhält unveränderliche gemeinsame Requirements aus
   `AGENTS.md`, `PLANNING.md` und den beiden Aufgaben. Er gleicht die Schnittstellen
   ab, erstellt gemeinsame Tests und committet die Testbasis samt Requirements.
4. Der Controller führt die deklarierten Tests erneut aus: ohne Netzwerk,
   Codex-Anmeldung, SSH-Agent oder Git-Schreibzugriff. Der Git-Helper ist in dieser
   Phase abgeschaltet. Ein erfolgreicher Modellprozess allein reicht nicht.
5. Bei grünen Prüfungen wird der Integrations-Feature-Branch gepusht. Nur dessen
   geprüfter Commit darf anschließend als Fast-forward auf Remote-`main` landen.
   Requirements und Worker-Aufgaben müssen weiterhin zu den getesteten Snapshots
   passen. Ein zwischenzeitlich geändertes Remote-`main` blockiert die Promotion.
6. Gemeinsames Ergebnis und Aufgaben erhalten `AUTO_VALIDATED`/`COMPLETED`;
   der Projektstatus zeigt `PROMOTED`. Es gibt keinen Accept-/Reject-Schritt.

Das Quellverzeichnis auf dem Host wird dabei nicht überschrieben. Nach erfolgreicher
Promotion steht das kombinierte Projekt auf GitHub auf `main`; die lokale Kopie
kann bei sauberem Arbeitsstand regulär mit Git aktualisiert werden.

## Gemeinsame Testbasis

Der Integrationsworker muss folgende Dateien committen:

- `validation/requirements.md`: exakte Kopie des gemeinsamen Requirements-Snapshots.
- `validation/plan.json`: Anforderung-zu-Test-Zuordnung und ausführbare Prüfsuiten.
- Die eigentlichen Tests, beispielsweise `tests/test_contract.py`.

```json
{
  "source_sha256": "SHA256 von validation/requirements.md",
  "requirements": [
    {"id": "REQ-1", "description": "Frontend und Backend verwenden denselben API-Vertrag",
     "checks": ["backend-tests", "frontend-tests"]}
  ],
  "checks": [
    {"id": "backend-tests", "kind": "pytest", "directory": "backend"},
    {"id": "frontend-tests", "kind": "npm", "directory": "frontend"}
  ]
}
```

Die SHA-256 stammt aus dem schreibgeschützten Snapshot unter
`.cafe/instructions/requirements.md`. Der Controller prüft Hash und Dateiinhalte.
Jede Anforderung muss auf vorhandene Checks verweisen, jeder Check muss einer
Anforderung zugeordnet sein. Doppelte IDs, unbekannte Ausführungsarten, Pfad-Traversal,
Symlinks und uncommittete Testpläne werden abgelehnt.

Unterstützte Checks:

| Art | Ausführung |
| --- | --- |
| `pytest` | Backend-Python `-m pytest -q -p no:cacheprovider` im angegebenen Projektordner |
| `npm` | `npm test`, mit `CI=1` |
| `godot` | Godot headless mit committetem Testscript, z. B. `"script": "tests/test_states.gd"` |

Projektabhängigkeiten müssen in der jeweiligen Testumgebung vorhanden sein; der
Controller installiert während der isolierten Prüfung keine Pakete aus dem Netz.
Testzuordnung und Testqualität werden vom Integrationsworker erstellt. Grüne
Prüfungen belegen die deklarierten Tests, keinen formalen Beweis aller Prosa-Anforderungen.

## Fehler, Wiederholung und Historie

**Executions** zeigt Worker-Status, Team-Status, Requirements-Prüfungen, Feature-
Push und Main-Promotion. Die Auswahl eines Worker-Laufs zeigt auch den aktuellen
Team-Status. Der Integrationslauf enthält Commit, Requirements-/Plan-Hashes,
Anforderungszuordnung und Check-Ergebnisse. Rohe Tool-Ausgaben und private Prompts
werden nicht in den öffentlichen Eventstream übernommen.

- `WAITING_FOR_WORKERS`: Erst fehlgeschlagenen/veralteten Worker korrigieren und
  erneut starten. Erfolgreiche andere Worktrees bleiben erhalten.
- `FAILED`: Integrationsfehler, Konflikt oder fehlgeschlagene gemeinsame Prüfung;
  `main` wird nicht automatisch mit dem fehlgeschlagenen Stand überschrieben.
- `INTERRUPTED`: Backend während der Integration beendet; bestehende Dateien bleiben.
- `PROMOTED`: Der getestete gemeinsame Commit wurde erfolgreich auf `main` gepusht.

Nach einer Korrektur kann **Retry team integration** im Ausführungsdialog den
Ablauf erneut anstoßen. Merge-Konflikte werden im Integrations-Worktree an den Integrationsagenten
übergeben. Er löst Inhalte auf, staged die aufgelösten Dateien und committet den
Merge. Retry kann auch einen zuvor unterbrochenen Merge wieder aufnehmen. Es gibt
kein automatisches Reset, Clean, Abort oder Force-Push.
Bei geändertem Main wird erneut zusammengeführt und getestet. Agenten desselben
Teams können während der laufenden Integration nicht neu gestartet werden.

Die Zustände und Ergebnisse überleben Backend-Neustarts. Unterbrochene Integration
wird nicht als Erfolg behandelt. Nach Neustart im Codex-Modus werden aktivierte
Teams wieder auf geeignete Worker-Ergebnisse geprüft.

## API und Nachweis

- Setup: `POST /management/setup/team` mit `auto_integrate: true` (impliziert
  `publish_results: true`), vorhandene Remote-Git-Freigabe erforderlich.
- Wiederholen: `POST /management/projects/{id}/integrate` mit `{}`.
- Status: Management-Übersicht (`projects`) und bestehende Execution-/Log-Endpunkte.
- Der bisherige `/executions/{id}/review`-Endpunkt bleibt für ältere API-Clients
  erhalten, ist aber keine Voraussetzung und kann keine Main-Promotion freigeben.

`test_team_integration.py` prüft mit echten temporären Git-Repositories und echten
isolierten pytest-Läufen die erfolgreiche Main-Promotion sowie Test-, Worker-,
Plan- und Merge-Fehler, konkurrierende Main-Updates und geänderte Requirements.
Das erfordert weder externe Git-Hosts noch Modellaufrufe.

### Retry zeigt keinen sichtbaren Start

Unter Executions steht der Team-Status direkt über **Retry team integration**.
Ein Klick zeigt sofort die Anfrage, anschließend `QUEUED`, `PREPARING`, den
konkreten Blockierungsgrund oder `PROMOTED`, wenn genau diese Worker-Ergebnisse
bereits integriert wurden. Eine angenommene Anfrage bedeutet noch keinen Abschluss.

Der Controller prüft vor dem Einreihen den jeweils neuesten Worker-Lauf. Die
Rückmeldung nennt den betroffenen Agenten und unterscheidet fehlende/laufende/
fehlgeschlagene Ausführungen, fehlende Veröffentlichung sowie geänderte Aufgaben,
Projekt-Markdown-Dateien oder Rollen. Bei geänderten Vorgaben reichen ältere
`COMPLETED`-/`PUSHED`-Ergebnisse nicht aus. Die Meldung wird auch bei automatisch
angestoßener Integration als Team-Status gespeichert.

Die letzte Retry-Antwort bleibt zusätzlich im kopierbaren Feld **LAST RETRY**
unter dem Button stehen. Automatische Log-Abfragen ändern nur den aktuellen
Team-Status darüber. Die Antwort ist dem ausgewählten Lauf zugeordnet und bleibt
beim Wechsel zwischen Läufen in derselben Godot-Sitzung erhalten. Eine neue
Retry-Anfrage für diesen Lauf ersetzt sie; nach einem Client-Neustart kann die
Antwort erneut angefordert werden.


### Konflikte und erneutes Team-Setup

Ein Git-Merge-Konflikt verhindert den Start des Integrationsagenten nicht mehr.
Er erhält die vorhandenen Dateien, den begonnenen Merge, die aktuellen Requirements
und die exakten benötigten Main-/Worker-Commits. Über den Git-Helper darf nur dieser
Agent die für seinen aktuellen Lauf freigegebenen Commits zusammenführen. Fremde
Commits, Branchwechsel und direkte Pushes werden darüber nicht freigegeben.

Vor Veröffentlichung und Requirements-Validierung prüft der Controller: keine
uncommitteten Projektänderungen, kein offener Merge und alle benötigten Commits in
der HEAD-Historie. Eine Erfolgsmeldung des Modells reicht nicht. Nicht lösbare
Konflikte bleiben als fehlgeschlagener Lauf mit erhaltenen Dateien zur erneuten
Bearbeitung verfügbar. Semantisch widersprüchliche Anforderungen können weiterhin
menschliche Klärung erfordern.

Einzeln gelöschte Worker werden beim erneuten Team-Setup wieder angelegt. Vorhandene
passende Worktrees, Branches und Markdown-Dateien werden weiterverwendet; die
Neueinrichtung verwirft keine lokale Arbeit und bedeutet keinen leeren Neustart.
