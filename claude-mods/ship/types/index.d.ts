export type ShipTree = {
  path: string
  name: string
  isCurrent: boolean
  /** commits on this worktree's HEAD that no remote branch has */
  unpushed: number
  /** files git status lists as changed or untracked */
  dirty: number
}

declare module 'claude-code' {
  interface PluginState {
    ship: {
      trees: ShipTree[]
      /** the band is hidden while the summary still reads this; '' when shown */
      hiddenFor: string
      /** the /ship step running now; '' when idle */
      running: string
    }
  }
}
