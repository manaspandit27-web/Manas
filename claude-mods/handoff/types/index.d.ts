export type HandoffEntry = {
  sessionId: string
  title: string
  /** the repository (worktrees share one) or the directory the session ran in */
  project: string
  cwd: string
  /** the handoff file, absolute; '' until one is written */
  path: string
  /** when the handoff was last written, ms since the epoch; 0 for none */
  at: number
  lastAt: number
}

declare module 'claude-code' {
  interface PluginState {
    handoff: {
      /** the earlier session offered on the band at startup; null for none */
      offer: HandoffEntry | null
      /** how many more recent handoffs this project has beyond the offer */
      more: number
      /** the handoff file attached to the next prompt; '' for none */
      pending: string
    }
  }
}
