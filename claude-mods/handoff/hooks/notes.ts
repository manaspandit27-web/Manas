// Pure helpers for the handoff mod.
import type { HandoffEntry } from '../types'

export const HANDOFF_PROMPT = `Write a handoff note so that a fresh Claude session, which has none of this conversation, can pick up this work. Markdown, under 400 words, with exactly these sections:
## Goal
What the user is trying to achieve, in their terms.
## State
What is done and verified: files, commits and branches, PRs, artifacts, URLs.
## In progress
What was underway when this note was written, and how far it got.
## Waiting on the user
Pending decisions or approvals, each phrased as a question.
## Next steps
Concrete steps, in order.
## Gotchas
Things learned the hard way: commands that fail, constraints, preferences the user stated.
Use only facts from this conversation and write "none" for an empty section. Output only the note.`

export function slug(text: string, max = 40): string {
  const s = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, max)
    .replace(/-+$/, '')
  return s === '' ? 'session' : s
}

export function ago(ms: number): string {
  const m = Math.round(ms / 60_000)
  if (m < 60) return `${Math.max(1, m)}m ago`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

export function stamp(now: number): string {
  const d = new Date(now)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
}

/** A title from the first words of a prompt, when no model is at hand. */
export function fallbackTitle(text: string): string {
  const words = text.replace(/\s+/g, ' ').trim().split(' ').slice(0, 6).join(' ')
  return words.length > 50 ? `${words.slice(0, 47)}…` : words
}

/** Whether what the user has said so far says enough to name the session. */
export const isNameable = (userText: string): boolean => userText.replace(/\s+/g, ' ').trim().length >= 25

export function cleanTitle(raw: string): string | undefined {
  const t = raw.split('\n')[0]?.replace(/^["'#*\s]+|["'.*\s]+$/g, '').trim() ?? ''
  return t === '' || t.length > 60 ? undefined : t
}

/** The recent handoffs of a project, newest first, other sessions only. */
export function recentFor(
  entries: readonly HandoffEntry[],
  project: string,
  sessionId: string,
  now: number,
  maxAgeMs = 7 * 86_400_000,
): HandoffEntry[] {
  return entries
    .filter(e => e.project === project && e.sessionId !== sessionId && e.path !== '' && now - e.at <= maxAgeMs)
    .sort((a, b) => b.at - a.at)
}

export function header(entry: HandoffEntry, now: number, reason: string): string {
  return `# Handoff: ${entry.title}\n\n_session ${entry.sessionId} · ${entry.cwd} · ${new Date(now).toLocaleString()} · written on ${reason} · resume with \`claude --resume ${entry.sessionId}\`_\n\n`
}

/** Reads the classifier's answer: the 1-based number of a candidate, or undefined. */
export function pickNumber(answer: string, count: number): number | undefined {
  const m = /\b(\d+)\b/.exec(answer)
  if (m === null || /\bnone\b/i.test(answer)) return undefined
  const n = Number(m[1])
  return n >= 1 && n <= count ? n - 1 : undefined
}

export function attachment(entry: HandoffEntry, text: string, now: number): string {
  return `[handoff mod] A handoff note from an earlier session on this project ("${entry.title}", ${ago(now - entry.at)}). Use it if the user is continuing that work:\n\n${text}`
}

export function shortHash(text: string): string {
  let h = 0
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) | 0
  return (h >>> 0).toString(36).slice(0, 5)
}

/** The "## Goal" section of a handoff, for telling notes apart. */
export function goalOf(note: string): string {
  const m = /##\s*Goal\s*\n([\s\S]*?)(\n##|$)/.exec(note)
  return (m?.[1] ?? note).replace(/\s+/g, ' ').trim().slice(0, 240)
}
