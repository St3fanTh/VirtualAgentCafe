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


def project_identity(path: Path) -> tuple[str, str]:
    remote = ""
    git_config = path / ".git" / "config"
    try:
        content = git_config.read_text(encoding="utf-8")
        if len(content) <= 131072:
            match = re.search(
                r'^\s*\[remote\s+"origin"\]\s*((?:(?!^\s*\[).*(?:\n|$))*)',
                content,
                re.MULTILINE,
            )
            if match:
                url = re.search(r"^\s*url\s*=\s*(.*?)\s*$", match.group(1), re.MULTILINE)
                remote = url.group(1) if url else ""
    except (OSError, UnicodeError):
        pass
    if re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", remote) or re.fullmatch(
        r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+", remote
    ):
        normalized = remote.lower().removesuffix(".git")
        slug = remote.rsplit("/", 1)[-1].rsplit(":", 1)[-1].removesuffix(".git")
        return hashlib.sha256(("remote:" + normalized).encode()).hexdigest(), slug
    resolved = str(path.resolve())
    return hashlib.sha256(("path:" + resolved).encode()).hexdigest(), path.name


def project_id(path: Path) -> str:
    identity, slug = project_identity(path)
    mapping = ROOT / ".runtime" / "setup" / "project-mounts.json"
    if mapping.is_file() and not mapping.is_symlink() and mapping.stat().st_size <= 65536:
        try:
            existing = json.loads(mapping.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get(identity), str):
                return existing[identity]
        except (OSError, json.JSONDecodeError):
            pass
    value = re.sub(r"[^a-z0-9_-]+", "-", slug.lower()).strip("-_")[:32]
    prefix = value if value and value[0].isalpha() else "project-" + value
    return prefix[:30] + "-" + identity[:8]


def save_project_id(path: Path, identifier: str) -> None:
    identity, _slug = project_identity(path)
    mapping = ROOT / ".runtime" / "setup" / "project-mounts.json"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if mapping.is_file() and not mapping.is_symlink() and mapping.stat().st_size <= 65536:
        try:
            value = json.loads(mapping.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                existing = value
        except (OSError, json.JSONDecodeError):
            pass
    existing[identity] = identifier
    temporary = mapping.with_suffix(".tmp")
    temporary.write_text(json.dumps(existing, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, mapping)


def selected_project(value: str | None) -> Path:
    if not value:
        if shutil.which("powershell.exe"):
            # A constant PowerShell program: selected paths are output, never shell code.
            script = """
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'VirtualAgentCafe: Git-Projektordner auswählen'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Write($dialog.SelectedPath)
}
$dialog.Dispose()
"""
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8-sig",
                check=True,
            )
            windows_path = result.stdout.strip()
            if not windows_path:
                raise ValueError("Kein Projekt ausgewählt")
            value = subprocess.run(
                ["wslpath", "-u", windows_path], capture_output=True, text=True, check=True
            ).stdout.strip()
        else:
            try:
                import tkinter
                from tkinter import filedialog

                window = tkinter.Tk()
                window.withdraw()
                value = filedialog.askdirectory(title="VirtualAgentCafe – Git-Projekt auswählen")
                window.destroy()
            except Exception:
                print(
                    "Ordnerdialog nicht verfügbar. Projektpfad eingeben (oder --project verwenden)."
                )
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
        "--workspace-id",
        help="Container-Arbeitsbereich-ID; für Reparatur vorhandener Agenten-Worktrees",
    )
    parser.add_argument(
        "--privileged", action="store_true", help="Explizit den lokalen Namespace-Override nutzen"
    )
    parser.add_argument(
        "--remote-checks",
        action="store_true",
        help="Lesende Remote-Prüfung im Assistenten erlauben",
    )
    parser.add_argument(
        "--publish-results",
        action="store_true",
        help="Remote Git für Pushes auf eigene Agenten-Branches erlauben",
    )
    parser.add_argument("--login", action="store_true", help="Codex-Anmeldung interaktiv öffnen")
    parser.add_argument("--godot", help="Pfad zur Godot-Executable (auch Godot.exe in WSL)")
    parser.add_argument("--no-godot", action="store_true", help="Nur Backend starten")
    parser.add_argument(
        "--dry-run", action="store_true", help="Nur Mount-Plan anzeigen; nichts starten/schreiben"
    )
    args = parser.parse_args()
    project = selected_project(args.project)
    identifier = args.workspace_id or project_id(project)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", identifier):
        raise ValueError(
            "Workspace-ID muss mit einem Kleinbuchstaben beginnen und nur a-z, 0-9, _ "
            "oder - enthalten"
        )
    plan = override(project, identifier, args.remote_checks or args.publish_results)
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
    save_project_id(project, identifier)
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
    probe = subprocess.run(
        [
            *compose,
            "exec",
            "-T",
            "backend",
            "bash",
            "-lc",
            "source scripts/environment.sh && "
            'python3 scripts/sandbox-diagnostics.py --workspace "$1"',
            "vac-sandbox-check",
            f"/workspaces/{identifier}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        try:
            detail = json.loads(probe.stdout)["detail"]
        except (ValueError, KeyError, TypeError):
            detail = (
                "Sandbox-Diagnose nicht verfügbar. "
                "Backend-Image neu bauen und Diagnose im Container starten."
            )
        print("Sandbox nicht bereit: " + str(detail))
        if args.privileged:
            print("Privileged wurde angefordert. Prüfe zusätzlich die Docker-/WSL-Hostrichtlinien.")
        raise ValueError(
            "Sandbox-Prüfung fehlgeschlagen. Codex-Login und Godot-Start wurden übersprungen."
        )
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
