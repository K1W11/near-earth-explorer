import { css, type Component } from 'dreamland/core'
import sendIcon from 'iconoir/icons/regular/send.svg?raw'
import { askAssistant, type Satellite } from '../api/backend'
import { IconoirIcon } from './IconoirIcon'

type PromptDockProps = {
  selectedSatellite: Satellite | null
}

export const PromptDock: Component<PromptDockProps, {
  textarea: HTMLTextAreaElement | null
  answer: string
  status: 'idle' | 'loading' | 'error'
  errorMessage: string
}> = function () {
  this.textarea = null
  this.answer = ''
  this.status = 'idle'
  this.errorMessage = ''

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    const query = this.textarea?.value.trim() ?? ''
    if (!query || this.status === 'loading') return

    const satellite = this.selectedSatellite
    const contextualQuery = satellite
      ? `Regarding the satellite ${satellite.name}: ${query}`
      : query
    this.status = 'loading'
    this.answer = ''
    this.errorMessage = ''
    try {
      const result = await askAssistant(contextualQuery)
      this.answer = result.response
      this.status = 'idle'
      if (this.textarea) this.textarea.value = ''
    } catch (error: unknown) {
      this.status = 'error'
      this.errorMessage = error instanceof Error ? error.message : 'Assistant request failed'
    }
  }

  return (
    <form class="prompt-dock" on:submit={submit}>
      <header>
        <strong>{use(this.selectedSatellite).map((satellite) => satellite ? satellite.name : 'Satellite explorer')}</strong>
        <small>{use(this.selectedSatellite).map((satellite) => satellite
          ? `Gemini will answer questions about ${satellite.name}.`
          : 'Gemini will answer questions about the satellites.')}</small>
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
      {use(this.status).map((status: 'idle' | 'loading' | 'error') => status === 'error'
        ? <p class="prompt-error" role="alert">{use(this.errorMessage)}</p>
        : null)}
      {use(this.answer).map((answer) => answer
        ? <p class="prompt-answer" aria-live="polite">{answer}</p>
        : null)}
    </form>
  )
}

PromptDock.style = css`
  :scope {
    position: relative;
    flex: 0 0 auto;
    align-self: center;
    z-index: 3;
    display: grid;
    gap: 6px;
    width: min(520px, calc(100% - 48px));
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

  :scope .prompt-answer,
  :scope .prompt-error {
    margin: 0;
    padding-top: 6px;
    border-top: 1px solid rgb(255 255 255 / 15%);
    font-size: 11px;
    line-height: 1.45;
  }

  :scope .prompt-error {
    color: #ff9d9d;
  }

`
