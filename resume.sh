#!/usr/bin/env bash
# Resume the development orchestrator; run from the host or use --local inside it.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
local_mode=false
privileged=false
ssh_forward=false
selection=(--last)
model=${VAC_ORCHESTRATOR_MODEL:-gpt-6-astra}
extra=()
while (($#)); do
  case "$1" in
    --local) local_mode=true; shift ;;
    --privileged) privileged=true; shift ;;
    --ssh) ssh_forward=true; shift ;;
    --pick) selection=(); shift ;;
    --session|--model)
      option=$1
      if (($# < 2)) || [[ -z $2 || $2 == -* ]]; then
        echo "$option requires a value" >&2; exit 2
      fi
      if [[ $option == --session ]]; then selection=("$2"); else model=$2; fi
      shift 2 ;;
    --) shift; extra=("$@"); break ;;
    -h|--help)
      cat <<'HELP'
Usage: ./resume.sh [--pick | --session ID] [--model MODEL] [--privileged] [--ssh]
       ./resume.sh --local [--pick | --session ID] [--model MODEL]
       ./resume.sh [options] -- [additional codex resume arguments]

Default: build/start the Compose codex development container and resume its last
/workspace session in YOLO mode with gpt-6-astra. Sessions/login persist in codex_home.
--pick         Open the session picker instead of resuming the latest session.
--session ID   Resume a specific session ID or name.
--model MODEL Override VAC_ORCHESTRATOR_MODEL (default: gpt-6-astra).
--privileged  Explicitly use compose.privileged.yaml for container capabilities.
--ssh         Forward the host SSH agent and read-only known_hosts for Git access.
--local       Already inside the development container: run Codex directly.

YOLO disables Codex sandboxing and approval prompts. Use a trusted development
container. It does not change the application's managed-agent security settings.
HELP
      exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done
if $local_mode && { $privileged || $ssh_forward; }; then
  echo "--privileged and --ssh must be applied on the host when creating the container" >&2
  exit 2
fi
cd -- "$repo_dir"
resume=(codex resume --dangerously-bypass-approvals-and-sandbox --model "$model")
if $local_mode; then
  command -v codex >/dev/null || { echo "Codex CLI is not installed" >&2; exit 1; }
  exec "${resume[@]}" --cd "$repo_dir" "${selection[@]}" "${extra[@]}"
fi
command -v docker >/dev/null || { echo "Docker is required on the host; inside the container use --local" >&2; exit 1; }
compose=(docker compose --project-directory "$repo_dir" -f "$repo_dir/compose.yaml")
# Preserve optional, manually configured development overrides.
if [[ -f "$repo_dir/compose.override.yaml" ]]; then
  compose+=(-f "$repo_dir/compose.override.yaml")
fi
if $privileged; then compose+=(-f "$repo_dir/compose.privileged.yaml"); fi
if $ssh_forward; then
  if [[ ! -S ${SSH_AUTH_SOCK:-} || ! -f ${HOME}/.ssh/known_hosts ]]; then
    echo "--ssh requires a running host SSH agent (SSH_AUTH_SOCK) and ~/.ssh/known_hosts" >&2
    exit 2
  fi
  compose+=(-f "$repo_dir/compose.ssh.yaml")
fi
exec "${compose[@]}" --profile dev run --build --rm --no-deps codex \
  "${resume[@]}" --cd /workspace "${selection[@]}" "${extra[@]}"
