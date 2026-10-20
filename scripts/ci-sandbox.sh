#!/usr/bin/env bash
# Prepare only the disposable GitHub runner; production hosts are never modified.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/environment.sh
if [[ "${GITHUB_ACTIONS:-}" != true ]]; then
  echo 'This setup is restricted to GitHub Actions runners.' >&2
  exit 2
fi
report=$(mktemp)
trap 'rm -f "$report"' EXIT
if python scripts/sandbox-diagnostics.py > "$report"; then
  cat "$report"
  exit 0
fi
cat "$report"
code=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["code"])' "$report")
echo "::notice title=Sandbox preflight::Initial sandbox result: $code"
if [[ "$code" == namespace_denied ]] &&
   [[ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || true)" == 1 ]]; then
  # Permit namespaces for the installed sandbox binary, keeping the host-wide
  # AppArmor restriction enabled for every other unconfined application.
  sudo tee /etc/apparmor.d/vac-ci-bwrap > /dev/null <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>
profile vac-ci-bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
PROFILE
  sudo apparmor_parser -r /etc/apparmor.d/vac-ci-bwrap
fi
python scripts/sandbox-diagnostics.py
