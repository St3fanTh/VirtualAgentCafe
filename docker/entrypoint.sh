#!/usr/bin/env bash
set -euo pipefail
# Authentication uses an externally forwarded SSH agent; no keys in the image.
exec "$@"
