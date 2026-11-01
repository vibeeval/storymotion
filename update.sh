#!/bin/sh
set -eu
storymotion_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 -B "$storymotion_root/tools/update_source.py" "$@"
