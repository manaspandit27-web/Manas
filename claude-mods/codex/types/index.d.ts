export type CodexRun = {
  status: 'idle' | 'running' | 'done' | 'failed'
  /** what is reviewed, as the pane names it: "uncommitted changes", "feature vs main" */
  scope: string
  startedAt: number
  /** the last lines Codex printed while it ran */
  log: string
  /** Codex's final message (the review), or why it failed */
  text: string
}

declare module 'claude-code' {
  interface PluginState {
    codex: { run: CodexRun }
  }
}
