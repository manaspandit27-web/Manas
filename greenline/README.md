# Green Line C, in Claude Code

This shows the next Green Line C trains at the two stops below, right under the Claude Code prompt. Use it to decide whether there's time to start a session before you head out.

- **Washington Square → Government Center** (eastbound)
- **St. Mary's Street → Cleveland Circle** (westbound)

```
🚋 Wash Sq → Gov Ctr 4m (2 stops), 11m · St Mary's → Clev Cir 2m (1 stop)
```

The line refreshes every 30 seconds. `/greenline` gives the next three trains at each stop, how many stops away each one is, and where it is right now:

```
Wash Sq → Gov Ctr (Green Line C)
  4 min · 2 stops away · at Cleveland Circle
  11 min

St Mary's → Clev Cir (Green Line C)
  2 min · 1 stop away · → Kenmore · Approaching
```

When a train has no stop count, it hasn't left its terminal yet. In that case only the MBTA's predicted time is shown.

## 5-minute alerts

When a train comes within 5 minutes of either stop, you get one alert for that train:

- a toast inside Claude Code, e.g. `🚋 Wash Sq → Gov Ctr: train in 5 min (3 stops away)`
- a macOS notification with a chime, so it reaches you even when you're in another app

Each train alerts only once. A train that's already under 5 minutes when you start a session alerts right away.

In `/config` you can:

- change the 5 minutes with `alert_minutes`
- turn off the macOS notification with `desktop_notify`, keeping only the toast

If several Claude Code windows are open, each one alerts.

The first macOS notification may ask for permission (it comes from "Script Editor"). Allow it in System Settings → Notifications.

## Setup on your laptop

1. Clone this repo somewhere permanent, e.g. `~/code/manas`.
2. Put your MBTA key in your shell profile (`~/.zshrc`), **not** in this repo:
   ```sh
   export MBTA_API_KEY="your-key-here"
   ```
   The key is optional. Without it the API allows 20 requests a minute, and this mod uses about 6. With a key the limit is 1000 a minute.
3. Load the mod in every Claude Code session by adding this to `~/.claude/settings.json` (merge it into the existing `env` block if you already have one):
   ```json
   {
     "env": {
       "CLAUDE_CODE_PLUGIN_DIRS": "~/code/manas/greenline/mod"
     }
   }
   ```
   To try it for one session only, run `claude --plugin-dir ~/code/manas/greenline/mod` instead.
4. Open a new terminal (so it picks up `MBTA_API_KEY`) and start `claude`. The 🚋 line shows up under the prompt within a few seconds.

To change the refresh rate, set `refresh_seconds` in `/config` (minimum 15).

## Without Claude Code

`greenline.py` does the same thing from any terminal. It needs only Python 3 (already on macOS) and nothing to install:

```sh
./greenline/greenline.py           # next trains at both stops
./greenline/greenline.py --watch   # full-screen, refreshes every 30s, alerts at 5 min
./greenline/greenline.py --line    # the one-line version
```

A handy alias: `alias gl=~/code/manas/greenline/greenline.py`.

## Changing the stops

Both versions keep the stops in one list: `WATCHES` at the top of `mod/hooks/mbta.ts` and of `greenline.py`. Each entry holds:

- a label
- the stop's parent-station id (`place-…`, from `https://api-v3.mbta.com/stops?filter[route]=Green-C`)
- the terminal the train is heading toward

The direction is looked up from that terminal's name, so you never have to remember which direction is 0 and which is 1.

## Files

| File | What it is |
| --- | --- |
| `mod/hooks/mbta.ts` | MBTA API calls and the "stops away" math |
| `mod/hooks/register.ts` | Claude Code wiring: status line, timer, `/greenline` |
| `mod/tests/greenline.test.ts` | Tests against canned MBTA responses (`claude plugin test greenline/mod`) |
| `greenline.py` | Standalone terminal version |
