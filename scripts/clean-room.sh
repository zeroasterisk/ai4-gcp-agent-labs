#!/usr/bin/env bash
# Start a throwaway shell that cannot see your existing developer setup.
#
# Everything that makes YOUR machine special - gcloud config and ADC, uv and pip
# caches, ~/.netrc, ~/.zshrc exports, active virtualenvs - lives under $HOME or in
# the environment. This points HOME at a fresh temp directory and strips the
# relevant variables, so you get an attendee's blank slate without touching, moving
# or deleting anything real.
#
# Your tools still work: PATH entries are absolute, so gcloud/uv/python are found.
# Only their STATE is new.
#
# Exit the shell (or Ctrl-D) and everything is gone. Nothing outside the temp dir
# is ever written.
set -euo pipefail

ROOM="$(mktemp -d "${TMPDIR:-/tmp}/cleanroom.XXXXXX")"
mkdir -p "$ROOM/home"

cat <<EOF

  Clean room: $ROOM/home
  Your real HOME is untouched. Type 'exit' to leave and discard everything.

EOF

exec env -i \
  HOME="$ROOM/home" \
  PATH="$PATH" \
  TERM="${TERM:-xterm-256color}" \
  SHELL=/bin/bash \
  LANG="${LANG:-en_US.UTF-8}" \
  TMPDIR="$ROOM" \
  CLOUDSDK_CONFIG="$ROOM/home/.config/gcloud" \
  PS1='(clean-room) \W $ ' \
  /bin/bash --noprofile --norc
