import { css, type Component } from 'dreamland/core'
import sendIcon from 'iconoir/icons/regular/send.svg?raw'
import arrowDownIcon from 'iconoir/icons/regular/nav-arrow-down.svg?raw'
import arrowUpIcon from 'iconoir/icons/regular/nav-arrow-up.svg?raw'
import { askAssistant, type Satellite } from '../api/backend'
import { IconoirIcon } from './IconoirIcon'
import { MarkdownContent } from './MarkdownContent'
import { NarrationPlayer } from './NarrationPlayer'

type PromptDockProps = {
  selectedSatellite: Satellite | null
  onNarration?: (message: string, error?: boolean, stop?: () => void) => void
}

type ConversationEntry = {
  id: number
  query: string
  response: string
  error: boolean
  responseId?: string
}

declare global {
  interface Window {
    populateDummyConversation?: (count?: number) => void
  }
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
}> = function (cx) {
  this.textarea = null
  this.conversationElement = null
  this.conversationList = null
  this.conversations = []
  this.conversationOpen = false
  this.conversationAtBottom = true
  this.status = 'idle'
  this.errorMessage = ''
  let nextConversationId = 0
  const scrollConversationToEnd = (behavior: ScrollBehavior = 'smooth') => {
    const list = this.conversationList
    if (!list) return
    list.scrollTo({ top: list.scrollHeight, behavior })
    this.conversationAtBottom = true
  }
  const scheduleScrollToEnd = () => {
    this.conversationAtBottom = true
    requestAnimationFrame(() => {
      requestAnimationFrame(() => scrollConversationToEnd())
    })
  }
  const openConversation = () => {
    if (this.conversationOpen) {
      scheduleScrollToEnd()
      return
    }
    this.conversationOpen = false
    requestAnimationFrame(() => {
      this.conversationOpen = true
      scheduleScrollToEnd()
    })
  }
  const updateConversationScroll = (event: Event) => {
    const list = event.currentTarget as HTMLElement
    this.conversationAtBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 8
  }
  const resizePrompt = (textarea: HTMLTextAreaElement) => {
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`
    textarea.style.overflowY = textarea.scrollHeight > 180 ? 'auto' : 'hidden'
  }
  const handlePromptKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    const textarea = event.currentTarget as HTMLTextAreaElement
    textarea.form?.requestSubmit()
  }
  cx.mount = () => {
    use(this.selectedSatellite).listen(() => {
      this.conversations = []
      this.conversationOpen = false
      this.conversationAtBottom = true
      this.status = 'idle'
      this.errorMessage = ''
      if (this.textarea) this.textarea.value = ''
    })
    window.populateDummyConversation = (count = 12) => {
      const entries = Array.from({ length: Math.max(1, Math.min(100, count)) }, (_, index) => ({
        id: nextConversationId++,
        query: `Test question ${index + 1}: how does this simulated orbital record change over time?`,
        response: `### Dummy response ${index + 1}\n\nThis is local test data for scrolling. It includes **bold text**, a list, and a [link](https://example.com) without making a Gemini request.\n\n- Orbital position\n- Tracking status`,
        error: false,
      }))
      this.conversations = [...this.conversations, ...entries]
      openConversation()
    }
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
    const conversationWasOpen = this.conversationOpen
    this.conversations = [
      ...this.conversations,
      { id: conversationId, query, response: '', error: false },
    ]
    if (conversationWasOpen) scheduleScrollToEnd()
    else openConversation()
    this.status = 'loading'
    this.errorMessage = ''
    try {
      const result = await askAssistant(contextualQuery)
      this.conversations = this.conversations.map((entry) => (
        entry.id === conversationId
          ? { ...entry, response: result.response, responseId: result.response_id }
          : entry
      ))
      scheduleScrollToEnd()
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
      scheduleScrollToEnd()
    }
  }

  return (
    <div class={use(this.conversationOpen).map((open) => `prompt-stack ${open ? 'is-conversation-open' : 'is-conversation-closed'}`)}>
      {use(this.conversations).map((entries) => entries.length > 0
        ? (
          <section class={use(this.conversationOpen).map((open) => `conversation-log ${open ? 'is-open' : 'is-closed'}`)} this={use(this.conversationElement)} aria-live="polite">
            <div class="conversation-log-content">
              <div class="conversation-list" this={use(this.conversationList)} on:scroll={updateConversationScroll}>
                {entries.map((entry) => (
                  <article class={entry.error ? 'is-error' : ''}>
                    <p class="conversation-query">{entry.query}</p>
                    {entry.response
                      ? (
                        <div class="conversation-response">
                          <MarkdownContent content={entry.response} />
                          {entry.responseId
                            ? (
                              <div class="response-narration">
                                <NarrationPlayer
                                  responseId={entry.responseId}
                                  compact
                                  onNotification={this.onNarration}
                                />
                              </div>
                            )
                            : null}
                        </div>
                      )
                      : <p class="conversation-response">Gemini is thinking...</p>}
                  </article>
                ))}
              </div>
              {use(this.conversationAtBottom).map((atBottom) => atBottom ? null : (
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
            </div>
          </section>
        )
        : null)}
      <form class="prompt-dock" on:submit={submit}>
        <header>
          <strong>{use(this.selectedSatellite).map((satellite) => satellite ? satellite.name : 'Satellite explorer')}</strong>
          <small>{use(this.selectedSatellite).map((satellite) => satellite
            ? `Gemini will answer questions about ${satellite.name}.`
            : 'Gemini will answer questions about the satellites.')}</small>
          {use(this.conversations).map((entries) => use(this.conversationOpen).map((open) => entries.length > 0
            ? (
              <div class="conversation-actions">
                <button
                  type="button"
                  class="conversation-toggle"
                  aria-label={open ? 'Close conversation' : 'Open conversation'}
                  title={open ? 'Close conversation' : 'Open conversation'}
                  on:click={() => {
                    this.conversationOpen = !open
                    if (!open) scheduleScrollToEnd()
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
            on:input={(event: Event) => resizePrompt(event.currentTarget as HTMLTextAreaElement)}
            on:keydown={handlePromptKeyDown}
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
    padding-top: calc(32px + var(--layout-gap));
    box-sizing: border-box;
    pointer-events: none;
  }

  :scope .conversation-log {
    position: relative;
    display: flex;
    flex-direction: column;
    flex: 0 1 auto;
    min-height: 0;
    margin-top: auto;
    width: 100%;
    max-height: min(70vh, calc(100% - 48px));
    overflow: hidden;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 6px;
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    color: rgb(255 255 255 / 85%);
    pointer-events: auto;
    transform-origin: bottom center;
    transition: max-height 220ms ease, opacity 220ms ease, transform 220ms ease;
  }

  :scope .conversation-log.is-open {
    max-height: min(70vh, calc(100% - 48px));
    opacity: 1;
    transform: translateY(0);
  }

  :scope .conversation-log.is-closed {
    max-height: 0;
    min-height: 0;
    margin-top: 0;
    border-color: transparent;
    opacity: 0;
    pointer-events: none;
    transform: translateY(8px);
  }

  :scope .conversation-log-content {
    position: relative;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    max-height: 100%;
    overflow: hidden;
  }

  :scope .conversation-actions {
    position: absolute;
    top: 0;
    right: 0;
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
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 4px;
    background: rgb(0 0 0 / 72%);
    color: white;
    line-height: 1;
    cursor: pointer;
  }

  :scope .conversation-bottom {
    position: absolute;
    bottom: 16px;
    right: 16px;
    z-index: 1;
  }

  :scope .conversation-toggle svg,
  :scope .conversation-bottom svg {
    width: 14px;
    height: 14px;
  }

  :scope .conversation-list {
    display: grid;
    flex: 1 1 auto;
    gap: 12px;
    width: 100%;
    padding: 16px;
    overflow-y: auto;
    scrollbar-width: none;
    min-height: 0;
    max-height: none;
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

  :scope .response-narration {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 8px;
  }

  :scope .response-narration .narration-transcript {
    flex: 1 1 100%;
    padding-left: 8px;
    color: rgb(255 255 255 / 62%);
    font-style: italic;
  }

  :scope .conversation-list article.is-error .conversation-response {
    color: #ff9d9d;
  }

  :scope .prompt-dock {
    pointer-events: auto;
    flex: none;
    height: fit-content;
    max-height: max-content;
    min-height: 0;
    width: 100%;
    max-width: none;
    align-self: end;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    box-sizing: border-box;
    padding: 16px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 6px;
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    color: rgb(255 255 255 / 85%);
    pointer-events: auto;
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
    flex: 0 0 auto;
    gap: 8px;
    align-items: stretch;
  }

  :scope textarea {
    flex: 1;
    min-width: 0;
    min-height: 34px;
    max-height: 180px;
    height: 34px;
    box-sizing: border-box;
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
