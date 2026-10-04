# Claude Code mods

Four mods for Claude Code. Each one is a plugin made of function hooks, built for Claude Code 2.1.289.

| Mod | What you get |
| --- | --- |
| `limits` | A status line showing your 5-hour and weekly limits with reset countdowns, toasts at 80% and 95%, and `/burn [12h] [model]`, which estimates whether a run of that length fits. At 95%, Claude is told to finish its current step, and a handoff is written. |
| `ship` | A band above the prompt listing unpushed commits and uncommitted files in each worktree. `/ship` runs tests, fast-forwards main, pushes and rebuilds, then prints a one-line receipt. |
| `codex` | `/codex-review` runs Codex's own review and shows it in a side pane, with **Send to Claude**, **Copy** and **Close** buttons. It also gives Claude an `mcp__codex__ask` tool for second opinions. |
| `handoff` | Names untitled sessions. Writes handoff notes on its own: after 31 idle minutes, before compaction, on exit or `/clear`, and near a usage limit. When you return to a project, it offers the last note, and it attaches the matching note automatically if your first message continues earlier work. Commands: `/handoff`, `/handoffs [n]`. |

## Install (local CLI and desktop app)

On the Mac, from a checkout of this branch:

```sh
git clone -b claude/claude-mods https://github.com/manaspandit27-web/Manas ~/claude-mods-src
~/claude-mods-src/claude-mods/install.sh
```

The script copies the four mods to `~/claude-mods/`, backs up `~/.claude/settings.json`, and adds the mods to `CLAUDE_CODE_PLUGIN_DIRS` while keeping every other setting. You can re-run it to update. If you'd rather do it by hand, copy the folders and list them in `~/.claude/settings.json`, separated by `:`:

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "~/claude-mods/limits:~/claude-mods/ship:~/claude-mods/codex:~/claude-mods/handoff"
  }
}
```

Every new session loads them, including sessions you drive through Remote Control. To try one mod for a single session, run `claude --plugin-dir ~/claude-mods/ship`.

## Setup per mod

- **ship**: add `.claude/ship.json` to each repo. If the file is missing, `/ship` asks Claude to run your usual ship routine and write the file for you.
  ```json
  { "main": "main", "remote": "origin", "test": ["npm test"], "rebuild": ["./scripts/rebuild-sandbox.sh"], "pushTo": "main" }
  ```
  - `"pushTo": "branch"` pushes only the current branch and leaves main alone.
  - Each test or rebuild step can run for up to 10 minutes.
- **codex**: needs the Codex CLI (`npm i -g @openai/codex`, then `codex login`). Use `/config` to set its path or model.
- **handoff**: notes go to `~/.claude/handoffs/<project>/` by default. In `/config`, switch the location to `project` to write them to `<repo>/.claude/handoffs/` instead. The idle delay and auto-naming are also set there.
- **limits**: change the 80/95 thresholds in `/config`. Set the wrap-up threshold to 0 to turn wrap-up off.

## Notes

- `/burn` builds its burn-rate history from the moment you install it, so it says "n/a" at first. The per-model rates are measured across your whole account, so sessions running at the same time count toward them too.
- Run a mod's tests with `claude plugin test <folder>`. Check a mod with `claude plugin validate <folder>`.
