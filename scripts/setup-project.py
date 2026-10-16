#!/usr/bin/env python3
"""Local, explicit project mount + Godot launcher. Run on Linux/WSL Docker host."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_id(path: Path) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", path.name.lower()).strip("-_")[:32]
    prefix = value if value and value[0].isalpha() else "project-" + value
    return prefix[:30] + "-" + hashlib.sha256(str(path).encode()).hexdigest()[:8]


def selected_project(value: str | None) -> Path:
    if not value:
        try:
            import tkinter
            from tkinter import filedialog

            window = tkinter.Tk()
            window.withdraw()
            value = filedialog.askdirectory(title="VirtualAgentCafe – Git-Projekt auswählen")
            window.destroy()
        except Exception:
            # Tk availability/display varies across WSL hosts. A path prompt is the fallback.
            print("Ordnerdialog nicht verfügbar. Projektpfad eingeben (oder --project verwenden).")
            value = input("Projektordner: ").strip()
    if not value:
        raise ValueError("Kein Projekt ausgewählt")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir() or not (path / ".git").is_dir() or (path / ".git").is_symlink():
        raise ValueError(
            "Bitte das Hauptverzeichnis eines Git-Repositories auswählen (kein Worktree)."
        )
    if path == Path.home() or path in Path.home().parents:
        raise ValueError("Bitte einen Projektunterordner auswählen, nicht das Home-Verzeichnis.")
    if path == ROOT or path in ROOT.parents or ROOT in path.parents:
        raise ValueError(
            "Bitte ein separates Projekt auswählen, nicht das VirtualAgentCafe-Verzeichnis."
        )
    return path


def override(project: Path, identifier: str, remote_checks: bool) -> dict:
    service = {
        "environment": {"VAC_MODE": "codex", "VAC_ALLOW_REMOTE_GIT": "1" if remote_checks else "0"},
        "volumes": [
            {"type": "bind", "source": str(project), "target": f"/workspaces/{identifier}"}
        ],
    }
    sock = os.getenv("SSH_AUTH_SOCK", "")
    hosts = Path.home() / ".ssh" / "known_hosts"
    if sock and Path(sock).is_socket() and hosts.is_file():
        service["environment"]["SSH_AUTH_SOCK"] = "/run/host-ssh-agent"
        service["volumes"] += [
            {"type": "bind", "source": str(Path(sock).resolve()), "target": "/run/host-ssh-agent"},
            {
                "type": "bind",
                "source": str(hosts),
                "target": "/home/node/.ssh/known_hosts",
                "read_only": True,
            },
        ]
    return {"services": {"backend": service}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Projektordner; ohne Angabe öffnet sich der Ordnerdialog")
    parser.add_argument(
        "--privileged", action="store_true", help="Explizit den lokalen Namespace-Override nutzen"
    )
    parser.add_argument(
        "--remote-checks",
        action="store_true",
        help="Lesende Remote-Prüfung im Assistenten erlauben",
    )
    parser.add_argument("--login", action="store_true", help="Codex-Anmeldung interaktiv öffnen")
    parser.add_argument("--godot", help="Pfad zur Godot-Executable (auch Godot.exe in WSL)")
    parser.add_argument("--no-godot", action="store_true", help="Nur Backend starten")
    parser.add_argument(
        "--dry-run", action="store_true", help="Nur Mount-Plan anzeigen; nichts starten/schreiben"
    )
    args = parser.parse_args()
    project = selected_project(args.project)
    identifier = project_id(project)
    plan = override(project, identifier, args.remote_checks)
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    if not shutil.which("docker"):
        raise ValueError(
            "Docker Compose fehlt. Diesen Starter auf dem Linux-/WSL-Docker-Host ausführen."
        )
    config_dir = ROOT / ".runtime" / "setup"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = config_dir / "project.compose.json"
    config.write_text(json.dumps(plan, indent=2) + "\n")
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "compose.yaml"),
    ]
    if args.privileged:
        compose += ["-f", str(ROOT / "compose.privileged.yaml")]
    compose += ["-f", str(config)]
    print(
        f"Projekt: {project}\nFreigegeben als: {identifier}\n"
        "Keine Agentenstarts, Pushes oder Merges."
    )
    if "SSH_AUTH_SOCK" not in plan["services"]["backend"]["environment"]:
        print("SSH-Agent/known_hosts nicht verfügbar. Lokales Arbeiten bleibt möglich.")
    subprocess.run([*compose, "up", "--build", "--wait", "backend"], check=True)
    login = subprocess.run(
        [*compose, "exec", "-T", "backend", "codex", "login", "status"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if args.login or login.returncode != 0:
        print("Codex-Anmeldung wird geöffnet. Danach geht die Einrichtung weiter.")
        subprocess.run([*compose, "exec", "backend", "codex", "login"], check=True)
    if args.no_godot:
        print("Backend bereit. Godot öffnen → Manage agents → Setup project.")
        return
    godot = args.godot or shutil.which("godot") or shutil.which("godot4")
    if not godot:
        print(
            "Backend bereit. Godot manuell öffnen oder erneut mit --godot /pfad/zu/Godot starten."
        )
        return
    # Read authorization directly into process memory; never print/store the token.
    token = subprocess.run(
        [*compose, "exec", "-T", "backend", "cat", "/workspace/.runtime/management/control-token"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    game = str(ROOT / "game")
    launch_env = {
        **os.environ,
        "VAC_MANAGEMENT_TOKEN": token,
        "VAC_OPEN_SETUP": "1",
        "VAC_BACKEND_URL": "http://127.0.0.1:8000",
        "VAC_SETUP_PROJECT": identifier,
    }
    if godot.lower().endswith(".exe"):
        game = subprocess.run(
            ["wslpath", "-w", game], check=True, capture_output=True, text=True
        ).stdout.strip()
        # WSL forwards only explicitly named variables to Windows executables.
        launch_env["WSLENV"] = (
            os.getenv("WSLENV", "")
            + ":VAC_MANAGEMENT_TOKEN:VAC_OPEN_SETUP:VAC_BACKEND_URL:VAC_SETUP_PROJECT"
        )
    subprocess.run([godot, "--path", game], env=launch_env, check=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Einrichtung angehalten: {error}", file=sys.stderr)
        sys.exit(1)
