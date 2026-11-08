import { css, type Component } from 'dreamland/core'

type NarrationLogProps = {
  onReady: (add: (message: string, error?: boolean, stop?: () => void) => void) => void
}

type Notification = { id: number; message: string; error: boolean; stop?: () => void }

export const NarrationLog: Component<NarrationLogProps, { items: Notification[]; element: HTMLElement | null }> = function () {
  this.items = []
  this.element = null
  let nextId = 0
  this.onReady((message, error = false, stop) => {
    this.items = [...this.items, { id: nextId++, message, error, stop }]
    queueMicrotask(() => {
      const container = this.element?.querySelector('.narration-log-list')
      if (container) container.scrollTop = container.scrollHeight
    })
  })

  return (
    <aside class="narration-log" this={use(this.element)} aria-live="polite">
      <div class="narration-log-list">
        {use(this.items).map((items) => items.map((item) => (
          <article class={item.error ? 'is-error' : ''}>
            <p>{item.message || 'Narration is ready.'}</p>
            <button type="button" aria-label="Dismiss narration notification" on:click={() => {
              item.stop?.()
              this.items = this.items.filter((candidate) => candidate.id !== item.id)
            }}>×</button>
          </article>
        )))}
      </div>
    </aside>
  )
}

NarrationLog.style = css`
  :scope {
    flex: 1 1 auto;
    align-self: stretch;
    display: flex;
    min-width: 0;
    min-height: 0;
    justify-content: flex-end;
    align-items: flex-end;
    z-index: 4;
    padding: 0 var(--layout-gap) 0 0;
    pointer-events: none;
  }
  :scope .narration-log-list {
    display: grid;
    width: min(360px, 100%);
    max-width: 100%;
    gap: 8px;
    max-height: 100%;
    overflow-y: auto;
    scrollbar-width: none;
  }
  :scope .narration-log-list::-webkit-scrollbar { display: none; }
  :scope article {
    position: relative;
    padding: 12px 34px 12px 14px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 6px;
    background: rgb(0 0 0 / 82%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    color: rgb(255 255 255 / 85%);
    pointer-events: auto;
  }
  :scope article.is-error { border-color: rgb(255 120 120 / 70%); }
  :scope p { margin: 0; font-size: 11px; line-height: 1.4; }
  :scope button {
    position: absolute;
    top: 6px;
    right: 8px;
    padding: 0;
    border: 0;
    background: transparent;
    color: white;
    font-size: 18px;
    cursor: pointer;
  }
`
