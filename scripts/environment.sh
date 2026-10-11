# Sourced by project entrypoints; works in WSL and rebuilt dev containers.
# The Codex shell may omit the image's /opt/venv from PATH.
vac_project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -x "$vac_project_root/.venv/bin/python" ]] && "$vac_project_root/.venv/bin/python" --version >/dev/null 2>&1; then
  export PATH="$vac_project_root/.venv/bin:$PATH"
elif [[ -x /opt/venv/bin/python ]]; then
  export PATH="/opt/venv/bin:$PATH"
fi
# Use the mounted source after git pull, rather than the version baked into the image.
export PYTHONPATH="$vac_project_root/backend${PYTHONPATH:+:$PYTHONPATH}"
