"""Email (SMTP out, IMAP in) and Slack (bot DMs) for the agent's own identity."""

from __future__ import annotations

import imaplib
import os
import re
import smtplib
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime

MAX_INBOUND_CHARS = 4000


@dataclass
class Inbound:
    sender_key: str
    channel: str
    received_at: str
    subject: str
    text: str


@dataclass
class Channels:
    """Sends and reads messages. With dry_run, sending only prints."""

    dry_run: bool = False
    bot_email: str = field(default_factory=lambda: os.environ.get("BOT_EMAIL", ""))
    bot_name: str = field(default_factory=lambda: os.environ.get("BOT_NAME", "DSAIL Course Agent"))

    def __post_init__(self):
        token = os.environ.get("SLACK_BOT_TOKEN")
        self.slack = None
        if token:
            from slack_sdk import WebClient

            self.slack = WebClient(token=token)
        self._slack_ids: dict[str, str] = {}

    # ---- email ----

    @property
    def email_enabled(self) -> bool:
        return bool(os.environ.get("SMTP_HOST") and self.bot_email)

    def send_email(self, to: str, subject: str, body: str, cc: list[str] | None = None) -> None:
        msg = EmailMessage()
        msg["From"] = f"{self.bot_name} <{self.bot_email}>"
        msg["To"] = to
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg.set_content(body)
        if self.dry_run:
            print(f"--- DRY RUN email to {to} (cc {cc}) ---\nSubject: {subject}\n\n{body}\n")
            return
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as smtp:
            smtp.starttls()
            smtp.login(os.environ.get("SMTP_USER", self.bot_email), os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)

    def read_email(self, people_by_email: dict[str, str]) -> tuple[list[Inbound], list[bytes]]:
        """Unread inbox mail from known people. Returns the messages and their IMAP ids,
        which mark_email_read() marks as read once the run has handled them. Mail from
        anyone else is left unread for a human."""
        if not os.environ.get("IMAP_HOST"):
            return [], []
        found, ids = [], []
        with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"]) as imap:
            imap.login(os.environ.get("IMAP_USER", self.bot_email), os.environ.get("IMAP_PASSWORD", os.environ["SMTP_PASSWORD"]))
            imap.select("INBOX", readonly=True)
            _, data = imap.search(None, "UNSEEN")
            for num in data[0].split():
                _, parts = imap.fetch(num, "(BODY.PEEK[])")
                msg = message_from_bytes(parts[0][1], policy=policy.default)
                sender = parseaddr(msg["From"])[1].lower()
                if sender not in people_by_email:
                    continue
                body = msg.get_body(preferencelist=("plain",))
                text = strip_quoted(body.get_content() if body else "")
                found.append(Inbound(
                    sender_key=people_by_email[sender],
                    channel="email",
                    received_at=parsedate_to_datetime(msg["Date"]).isoformat() if msg["Date"] else "",
                    subject=str(msg["Subject"] or ""),
                    text=clip(text),
                ))
                ids.append(num)
        return found, ids

    def mark_email_read(self, ids: list[bytes]) -> None:
        if self.dry_run or not ids:
            return
        with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"]) as imap:
            imap.login(os.environ.get("IMAP_USER", self.bot_email), os.environ.get("IMAP_PASSWORD", os.environ["SMTP_PASSWORD"]))
            imap.select("INBOX")
            for num in ids:
                imap.store(num, "+FLAGS", "\\Seen")

    # ---- slack ----

    def slack_user_id(self, email: str) -> str:
        if email not in self._slack_ids:
            self._slack_ids[email] = self.slack.users_lookupByEmail(email=email)["user"]["id"]
        return self._slack_ids[email]

    def _dm_channel(self, email: str) -> str:
        return self.slack.conversations_open(users=self.slack_user_id(email))["channel"]["id"]

    def send_slack(self, email: str, text: str) -> None:
        if self.dry_run:
            print(f"--- DRY RUN Slack DM to {email} ---\n{text}\n")
            return
        self.slack.chat_postMessage(channel=self._dm_channel(email), text=text)

    def read_slack(self, people: dict[str, str], oldest_ts: str) -> tuple[list[Inbound], str]:
        """DMs people sent the bot since oldest_ts. people maps key -> Slack email.
        Returns the messages and the newest timestamp seen."""
        if not self.slack:
            return [], oldest_ts
        found, newest = [], oldest_ts
        for key, email in people.items():
            user_id = self.slack_user_id(email)
            history = self.slack.conversations_history(channel=self._dm_channel(email), oldest=oldest_ts, limit=100)
            for m in history["messages"]:
                if m.get("user") != user_id or m.get("bot_id"):
                    continue
                found.append(Inbound(key, "slack", m["ts"], "", clip(m.get("text", ""))))
                newest = max(newest, m["ts"], key=float)
        return found, newest


def strip_quoted(text: str) -> str:
    """Drop the quoted earlier message from an email reply."""
    lines = []
    for line in text.splitlines():
        if line.startswith(">") or re.match(r"^On .+ wrote:$", line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def clip(text: str) -> str:
    return text if len(text) <= MAX_INBOUND_CHARS else text[:MAX_INBOUND_CHARS] + "\n[message cut off here]"
