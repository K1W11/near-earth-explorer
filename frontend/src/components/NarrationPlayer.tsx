import { css, type Component } from 'dreamland/core'
import { narrateTarget, type NarrationTargetType } from '../api/backend'

type NarrationPlayerState = {
  status: 'idle' | 'loading' | 'playing' | 'error'
  transcript: string
  errorMessage: string
}

/**
 * "Hear the story" button for one map object.
 *
 * Usage: <NarrationPlayer name="ISS (ZARYA)" type="satellite" />
 * Must be started by a click: browsers block audio that starts on its own.
 */
export const NarrationPlayer: Component<
  { name: string; type: NarrationTargetType },
  NarrationPlayerState
> = function () {
  this.status = 'idle'
  this.transcript = ''
  this.errorMessage = ''

  let audio: HTMLAudioElement | undefined
  let audioUrl: string | undefined
  let latestRequest = 0

  const release = () => {
    audio?.pause()
    audio = undefined
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    audioUrl = undefined
  }

  const play = async () => {
    release()
    const request = ++latestRequest // ignore results of superseded clicks
    this.status = 'loading'
    this.errorMessage = ''

    try {
      const narration = await narrateTarget(this.name, this.type)
      if (request !== latestRequest) {
        URL.revokeObjectURL(narration.audioUrl)
        return
      }

      audioUrl = narration.audioUrl
      audio = new Audio(audioUrl)
      audio.addEventListener('ended', () => {
        if (request === latestRequest) this.status = 'idle'
      })
      this.transcript = narration.transcript
      await audio.play()
      if (request === latestRequest) this.status = 'playing'
    } catch (error) {
      if (request !== latestRequest) return
      this.status = 'error'
      this.errorMessage = error instanceof DOMException && error.name === 'NotAllowedError'
        ? 'Your browser blocked playback. Press the button again.'
        : error instanceof Error ? error.message : 'Narration failed'
    }
  }

  return (
    <div class="narration-player">
      <button
        type="button"
        attr:disabled={use(this.status).map((status) => status === 'loading')}
        on:click={play}
      >
        {use(this.status).map((status) => {
          if (status === 'loading') return 'Generating voice...'
          if (status === 'playing') return 'Play again'
          return 'Hear the story'
        })}
      </button>
      {use(this.status).map((status) => (
        status === 'error'
          ? <p class="error" role="alert">{use(this.errorMessage)}</p>
          : <p class="transcript" aria-live="polite">{use(this.transcript)}</p>
      ))}
    </div>
  )
}

NarrationPlayer.style = css`
  :scope {
    margin-top: 12px;
  }

  :scope button {
    padding: 8px 14px;
    color: white;
    background: #242424;
    border: 1px solid rgb(255 255 255 / 30%);
    border-radius: 6px;
    cursor: pointer;
  }

  :scope button:hover:not(:disabled) {
    background: #444;
  }

  :scope button:disabled {
    opacity: 0.6;
    cursor: progress;
  }

  :scope button:focus-visible {
    outline: 3px solid #9db8ff;
    outline-offset: 3px;
  }

  :scope p {
    margin: 10px 0 0;
    font-size: 14px;
    line-height: 1.5;
  }

  :scope .error {
    color: #ff9d9d;
  }
`
