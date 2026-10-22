# DSAIL course agent

A project-manager agent for the DSAIL course. Every weekday morning it:

1. Sends any reminders you approved since the last run.
2. Reads replies people sent it, by email or Slack DM, since the last run.
3. Gives Claude the tracker and those replies. Claude records progress, works out what is overdue, due soon or stalled, and writes reminders. Reminders for a professor's deliverables go to their FSS assistant.
4. Emails you, and DMs you on Slack, a short digest: what needs your decision, what's at risk, and what it did.

The agent has its own email address and its own Slack bot. People can reply to either one, and the next run picks the reply up.

## How it fits together

| Piece | Where |
|---|---|
| Tracker: Deliverables, People, Messages and State tabs | A Google Sheet (`course_agent/store.py`) |
| Agent loop and its two tools: `update_deliverable` and `send_message` | `course_agent/agent.py`, using Claude through the Anthropic API |
| Email out (SMTP) and in (IMAP); Slack DMs | `course_agent/channels.py` |
| Instructions | `prompts/system.md` (how it works) and `course.md` (about the course; edit this one) |
| Schedule | `.github/workflows/course-agent.yml` (GitHub Actions, weekdays) |

### Guardrails, enforced in code rather than left to the prompt
- It can only contact people listed in the People tab.
- **Approval mode** is on by default (`require_approval` in `config.toml`). A message to anyone but you is queued in the Messages tab as `pending`, and the digest lists it. Change its status to `approved` and the next run sends it, or to `rejected` to drop it. Set `require_approval = false` once you trust it.
- It sends at most one message per person per run.
- It won't remind the same person about the same deliverable again within `min_days_between` days.
- It never changes due dates. Requests to move a date come to you in the digest.
- It only reads email and Slack from people in the People tab. Mail from anyone else stays unread for a human.
- `--dry-run` prints everything it would send and writes nothing.

## Setup (about an hour, once)

### 1. Anthropic API key
Create a key at console.anthropic.com. This is billed per use, separately from a Claude subscription. One run a day costs cents.

### 2. The tracker sheet
1. Create a Google Sheet. Copy its ID from the URL: `docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.
2. In Google Cloud Console, create a project, enable the **Google Sheets API**, then create a **service account** and download its JSON key.
3. Share the sheet with the service account's email (`…@….iam.gserviceaccount.com`) as **Editor**.
4. Create the tabs: `SHEET_ID=… GOOGLE_SERVICE_ACCOUNT_JSON="$(cat key.json)" python -m course_agent init-sheet`
5. Fill in **People** and **Deliverables**. The files in `sample_data/` show the format.
   - `contact_via`: for each professor, the key of their FSS assistant, so reminders about the professor's items go to the assistant.
   - `channels`: `email`, `slack` or `email,slack`.
   - Dates are written `YYYY-MM-DD`.

### 3. The agent's email address
Create a mailbox for the agent, for example a new Gmail account like `dsail.course.agent@gmail.com`, or a university-issued one.
- For Gmail: turn on 2-step verification, then create an **App password**. Use `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `IMAP_HOST=imap.gmail.com`, and the app password as `SMTP_PASSWORD`.
- Without `IMAP_HOST`, the agent still sends email but doesn't read replies.

### 4. The Slack bot (optional; email works without it)
1. At api.slack.com/apps, choose **Create New App**, then **From scratch**, and pick the course workspace.
2. Under **OAuth & Permissions**, add these bot scopes: `chat:write`, `im:write`, `im:history`, `users:read`, `users:read.email`.
3. Under **App Home**, turn on the **Messages tab** and tick "Allow users to send messages", so people can reply to the bot.
4. Install it to the workspace and copy the **Bot User OAuth Token** (`xoxb-…`) as `SLACK_BOT_TOKEN`.

University workspaces often need an admin to approve new apps, so ask early. The bot can only DM people who are in that workspace.

### 5. Put it on a schedule
Push this folder as its own GitHub repository (private). Then, under **Settings → Secrets and variables → Actions**, add these secrets:
`ANTHROPIC_API_KEY`, `SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the whole JSON), `BOT_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_PASSWORD`, `IMAP_HOST`, `SLACK_BOT_TOKEN`.

Next, go to **Actions → Course agent → Run workflow**. "dry run" is ticked by default, so you can check the output before anything is sent. After that, it runs on its own every weekday. GitHub cron uses UTC, so set the time in the workflow file.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=…  BOT_EMAIL=…  # plus whichever channels you've set up
python -m course_agent run --dry-run          # nothing is sent or written
```

To try it without Google at all, set `backend = "local"` in `config.toml`. The agent then uses the CSV files in `sample_data/`.

## Tuning
- `config.toml` sets your time zone, the "due soon" and "stalled" thresholds, the gap between reminders, approval mode, and the model and effort level.
- `course.md` holds what the agent should know about the course and the professors, such as hard deadlines, preferred tone, and busy weeks to avoid.
- `prompts/system.md` holds the general rules: what to remind about, how to write messages, and the digest format.
