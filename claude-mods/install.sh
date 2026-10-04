#!/bin/sh
# Installs the four mods into ~/claude-mods and lists them in ~/.claude/settings.json
# (env.CLAUDE_CODE_PLUGIN_DIRS), keeping every other setting and any plugin dirs
# already listed. Safe to run again: it updates the copies and changes nothing else.
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
DEST="${CLAUDE_MODS_DIR:-$HOME/claude-mods}"
SETTINGS="$HOME/.claude/settings.json"
MODS="limits ship codex handoff"

mkdir -p "$DEST" "$HOME/.claude"
for m in $MODS; do
  rm -rf "${DEST:?}/$m.new"
  cp -R "$SRC/$m" "$DEST/$m.new"
  rm -rf "${DEST:?}/$m"
  mv "$DEST/$m.new" "$DEST/$m"
  echo "copied $m -> $DEST/$m"
done

if [ -f "$SETTINGS" ]; then
  cp "$SETTINGS" "$SETTINGS.bak-claude-mods"
  echo "backed up $SETTINGS -> $SETTINGS.bak-claude-mods"
fi

DEST="$DEST" SETTINGS="$SETTINGS" MODS="$MODS" python3 - <<'PY'
import json, os
settings_path = os.environ["SETTINGS"]
dest = os.environ["DEST"]
mods = os.environ["MODS"].split()
try:
    with open(settings_path) as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}
env = settings.setdefault("env", {})
existing = [p for p in env.get("CLAUDE_CODE_PLUGIN_DIRS", "").split(":") if p]
wanted = [os.path.join(dest, m) for m in mods]
expanded = {os.path.expanduser(p) for p in existing}
env["CLAUDE_CODE_PLUGIN_DIRS"] = ":".join(existing + [p for p in wanted if p not in expanded])
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
print("CLAUDE_CODE_PLUGIN_DIRS =", env["CLAUDE_CODE_PLUGIN_DIRS"])
PY

for m in $MODS; do
  if command -v claude >/dev/null 2>&1; then
    claude plugin validate "$DEST/$m" 2>&1 | tail -1 | sed "s/^/$m: /"
  fi
done
command -v codex >/dev/null 2>&1 || echo "note: Codex CLI not found; /codex-review needs it (npm i -g @openai/codex, then codex login)"
echo "Done. New Claude Code sessions load the mods; restart any session that is already open."
