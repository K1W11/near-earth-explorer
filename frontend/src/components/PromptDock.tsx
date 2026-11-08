import { css, type Component } from 'dreamland/core'
import sendIcon from 'iconoir/icons/regular/send.svg?raw'
import arrowDownIcon from 'iconoir/icons/regular/nav-arrow-down.svg?raw'
import arrowUpIcon from 'iconoir/icons/regular/nav-arrow-up.svg?raw'
import { askAssistant, type Satellite } from '../api/backend'
import { IconoirIcon } from './IconoirIcon'

type PromptDockProps = {
  selectedSatellite: Satellite | null
}

type ConversationEntry = {
  id: number
  query: string
  response: string
  error: boolean
}

export const PromptDock: Component<PromptDockProps, {
  textarea: HTMLTextAreaElement | null
  conversationElement: HTMLElement | null
  conversationList: HTMLElement | null
  conversations: ConversationEntry[]
  conversationOpen: boolean
  conversationAtBottom: boolean
  status: 'idle' | 'loading' | 'error'
  errorMessage: string
}> = function () {
  this.textarea = null
  this.conversationElement = null
  this.conversationList = null
  this.conversations = []
  this.conversationOpen = true
  this.conversationAtBottom = true
  this.status = 'idle'
  this.errorMessage = ''
  let nextConversationId = 0
  const scrollConversationToEnd = () => {
    queueMicrotask(() => {
      const list = this.conversationList
      if (list) {
        list.scrollTop = list.scrollHeight
        this.conversationAtBottom = true
      }
    })
  }
  const updateConversationScroll = (event: Event) => {
    const list = event.currentTarget as HTMLElement
    this.conversationAtBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 8
  }

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    const query = this.textarea?.value.trim() ?? ''
    if (!query || this.status === 'loading') return

    const satellite = this.selectedSatellite
    const contextualQuery = satellite
      ? `Regarding the satellite ${satellite.name}: ${query}`
      : query
    const conversationId = nextConversationId++
    this.conversations = [
      ...this.conversations,
      { id: conversationId, query, response: '', error: false },
    ]
    scrollConversationToEnd()
    this.status = 'loading'
    this.errorMessage = ''
    try {
      const result = await askAssistant(contextualQuery)
      this.conversations = this.conversations.map((entry) => (
        entry.id === conversationId ? { ...entry, response: result.response } : entry
      ))
      scrollConversationToEnd()
      this.status = 'idle'
      if (this.textarea) this.textarea.value = ''
    } catch (error: unknown) {
      this.status = 'error'
      this.errorMessage = error instanceof Error ? error.message : 'Assistant request failed'
      this.conversations = this.conversations.map((entry) => (
        entry.id === conversationId
          ? { ...entry, response: this.errorMessage, error: true }
          : entry
      ))
      scrollConversationToEnd()
    }
  }

  return (
    <div class="prompt-stack">
      {use(this.conversations).map((entries) => use(this.conversationOpen).map((open) => entries.length > 0 && open
        ? (
          <section class="conversation-log" this={use(this.conversationElement)} aria-live="polite">
            <div class="conversation-list" this={use(this.conversationList)} on:scroll={updateConversationScroll}>
              {entries.map((entry) => (
                <article class={entry.error ? 'is-error' : ''}>
                  <p class="conversation-query">{entry.query}</p>
                  <p class="conversation-response">
                    {entry.response || 'Gemini is thinking...'}
                  </p>
                </article>
              ))}
            </div>
          </section>
        )
        : null))}
      <form class="prompt-dock" on:submit={submit}>
        <header>
          <strong>{use(this.selectedSatellite).map((satellite) => satellite ? satellite.name : 'Satellite explorer')}</strong>
          <small>{use(this.selectedSatellite).map((satellite) => satellite
            ? `Gemini will answer questions about ${satellite.name}.`
            : 'Gemini will answer questions about the satellites.')}</small>
          {use(this.conversations).map((entries) => use(this.conversationOpen).map((open) => entries.length > 0
            ? (
              <div class="conversation-actions">
                {open && use(this.conversationAtBottom).map((atBottom) => atBottom ? null : (
                  <button
                    type="button"
                    class="conversation-bottom"
                    aria-label="Scroll to newest conversation entry"
                    title="Scroll to newest"
                    on:click={scrollConversationToEnd}
                  >
                    <IconoirIcon svg={arrowDownIcon} />
                  </button>
                ))}
                <button
                  type="button"
                  class="conversation-toggle"
                  aria-label={open ? 'Close conversation' : 'Open conversation'}
                  title={open ? 'Close conversation' : 'Open conversation'}
                  on:click={() => {
                    this.conversationOpen = !open
                    if (!open) scrollConversationToEnd()
                  }}
                >
                  <IconoirIcon svg={open ? arrowDownIcon : arrowUpIcon} />
                </button>
              </div>
            )
            : null))}
        </header>
        <div class="prompt-row">
          <textarea
            id="orbit-prompt"
            this={use(this.textarea)}
            rows="1"
            placeholder="Ask a question about this view..."
            aria-label="Ask Gemini about the satellites"
          ></textarea>
          <button
            type="submit"
            aria-label="Send prompt"
            title={use(this.status).map((status: 'idle' | 'loading' | 'error') => status === 'loading' ? 'Waiting for Gemini' : 'Send prompt')}
            attr:disabled={use(this.status).map((status: 'idle' | 'loading' | 'error') => status === 'loading')}
          >
            <IconoirIcon svg={sendIcon} />
          </button>
        </div>
      </form>
    </div>
  )
}

PromptDock.style = css`
  :scope {
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    flex: 1 1 auto;
    align-self: stretch;
    z-index: 3;
    width: 100%;
    min-width: 0;
    min-height: 0;
    gap: var(--layout-gap);
  }

  :scope .conversation-log {
    display: flex;
    flex-direction: column;
    flex: 0 1 min(360px, calc(100% - 48px));
    min-height: 0;
    margin-top: auto;
    width: 100%;
    overflow: hidden;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 6px;
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    color: rgb(255 255 255 / 85%);
  }

  :scope .conversation-actions {
    position: absolute;
    top: 8px;
    right: 10px;
    display: flex;
    gap: 4px;
    align-items: center;
  }

  :scope .prompt-dock > header {
    position: relative;
    padding-right: 56px;
  }

  :scope .conversation-toggle,
  :scope .conversation-bottom {
    width: 24px;
    height: 24px;
    padding: 0;
    border: 0;
    background: transparent;
    color: white;
    line-height: 1;
    cursor: pointer;
  }

  :scope .conversation-toggle svg,
  :scope .conversation-bottom svg {
    width: 14px;
    height: 14px;
  }

  :scope .conversation-list {
    display: grid;
    gap: 12px;
    width: 100%;
    padding: 12px 14px;
    overflow-y: auto;
    scrollbar-width: none;
  }

  :scope .conversation-list::-webkit-scrollbar {
    display: none;
  }

  :scope .conversation-list article {
    display: grid;
    gap: 6px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgb(255 255 255 / 15%);
  }

  :scope .conversation-list article:last-child {
    padding-bottom: 0;
    border-bottom: 0;
  }

  :scope .conversation-list p {
    margin: 0;
    font-size: 11px;
    line-height: 1.45;
  }

  :scope .conversation-query {
    color: rgb(255 255 255 / 55%);
  }

  :scope .conversation-response {
    white-space: pre-wrap;
  }

  :scope .conversation-list article.is-error .conversation-response {
    color: #ff9d9d;
  }

  :scope .prompt-dock {
    width: 100%;
    max-width: none;
    align-self: end;
    display: grid;
    gap: 6px;
    box-sizing: border-box;
    padding: 12px 14px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 6px;
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    color: rgb(255 255 255 / 85%);
  }

  :scope header {
    display: grid;
    gap: 2px;
  }

  :scope header strong {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  :scope header small {
    color: rgb(255 255 255 / 52%);
    font-size: 10px;
  }

  :scope .prompt-row {
    display: flex;
    gap: 8px;
  }

  :scope textarea {
    flex: 1;
    min-width: 0;
    resize: none;
    padding: 8px 10px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 4px;
    outline: 0;
    background: rgb(255 255 255 / 8%);
    color: white;
    font: inherit;
    font-size: 12px;
  }

  :scope textarea:focus {
    border-color: rgb(98 217 255 / 80%);
  }

  :scope textarea::placeholder {
    color: rgb(255 255 255 / 48%);
  }

  :scope button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 4px;
    background: rgb(255 255 255 / 8%);
    color: white;
  }

  :scope button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

`
