// Pure helpers for the ship mod: parsing git output and reading commands.

export type Worktree = { path: string; branch: string | null; isBare: boolean; isPrunable: boolean }

export type ShipConfig = {
  /** the branch that gets fast-forwarded and pushed; default "main" */
  main: string
  /** default "origin" */
  remote: string
  /** shell commands that must pass before anything is pushed */
  test: string[]
  /** shell commands run after the push (rebuild a sandbox, deploy) */
  rebuild: string[]
  /** "main": fast-forward main to this branch and push it; "branch": push only this branch */
  pushTo: 'main' | 'branch'
  /** block the model's own pushes to main until /red-team ran this session */
  redTeamGate: boolean
}

export function parseWorktrees(porcelain: string): Worktree[] {
  const out: Worktree[] = []
  for (const block of porcelain.split(/\n\s*\n/)) {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean)
    const path = lines.find(l => l.startsWith('worktree '))?.slice('worktree '.length)
    if (path === undefined) continue
    const ref = lines.find(l => l.startsWith('branch '))?.slice('branch '.length)
    out.push({
      path,
      branch: ref === undefined ? null : ref.replace(/^refs\/heads\//, ''),
      isBare: lines.includes('bare'),
      isPrunable: lines.some(l => l.startsWith('prunable')),
    })
  }
  return out
}

export const basename = (path: string): string => path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? path

export function parseConfig(text: string | undefined): ShipConfig | undefined {
  if (text === undefined) return undefined
  const raw = JSON.parse(text) as Record<string, unknown>
  const list = (v: unknown): string[] =>
    typeof v === 'string' ? [v] : Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
  return {
    main: typeof raw.main === 'string' ? raw.main : 'main',
    remote: typeof raw.remote === 'string' ? raw.remote : 'origin',
    test: list(raw.test),
    rebuild: list(raw.rebuild),
    pushTo: raw.pushTo === 'branch' ? 'branch' : 'main',
    redTeamGate: raw.redTeamGate !== false,
  }
}

/**
 * Whether a shell command pushes to `main`: an explicit `main` / `HEAD:main`
 * refspec, or a bare `git push` while `main` is checked out.
 */
export function pushesTo(command: string, main: string, current: string | null): boolean {
  const pushes = [...command.matchAll(/\bgit\b(?:\s+-C\s+\S+)?\s+push\b([^;&|\n]*)/g)]
  return pushes.some(m => {
    const args = (m[1] ?? '').split(/\s+/).filter(a => a !== '' && !a.startsWith('-'))
    const specs = args.slice(1) // first is the remote
    if (specs.length === 0) return current === main
    return specs.some(s => {
      const dest = s.replace(/^\+/, '').split(':').pop()
      return dest === main || dest === `refs/heads/${main}` || (dest === 'HEAD' && current === main)
    })
  })
}

export function tail(text: string, lines = 12): string {
  return text.trimEnd().split('\n').slice(-lines).join('\n')
}

export type TreeCounts = { name: string; isCurrent: boolean; unpushed: number; dirty: number }

/** One line naming what is unpushed and what is uncommitted; '' when nothing is. */
export function summarize(trees: readonly TreeCounts[]): string {
  const mark = (t: TreeCounts) => `${t.name}${t.isCurrent ? '*' : ''}`
  const up = trees.filter(t => t.unpushed > 0).map(t => `${mark(t)} +${t.unpushed}`)
  const dirty = trees.filter(t => t.dirty > 0).map(t => `${mark(t)} ${t.dirty}`)
  const parts: string[] = []
  if (up.length > 0) parts.push(`⇡ unpushed: ${up.join(', ')}`)
  if (dirty.length > 0) parts.push(`✎ uncommitted: ${dirty.join(', ')}`)
  return parts.join('  ·  ')
}
