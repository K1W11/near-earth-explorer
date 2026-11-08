import { css, type Component } from 'dreamland/core'
import { narrateTarget, type NarrationTargetType, type SatelliteNarrationCategory } from '../api/backend'
import speakerIcon from 'iconoir/icons/regular/sound-high.svg?raw'
import { IconoirIcon } from './IconoirIcon'

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
  { name: string; type: NarrationTargetType; category?: SatelliteNarrationCategory; compact?: boolean; disabled?: boolean; onNotification?: (message: string, error?: boolean, stop?: () => void) => void },
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

  const stop = () => {
    latestRequest++
    release()
    this.status = 'idle'
  }

  const play = async () => {
    release()
    const request = ++latestRequest // ignore results of superseded clicks
    this.status = 'loading'
    this.errorMessage = ''

    try {
      const narration = await narrateTarget(this.name, this.type, this.category)
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
      this.onNotification?.(narration.transcript, false, stop)
      await audio.play()
      if (request === latestRequest) this.status = 'playing'
    } catch (error) {
      if (request !== latestRequest) return
      this.status = 'error'
      this.errorMessage = error instanceof DOMException && error.name === 'NotAllowedError'
        ? 'Your browser blocked playback. Press the button again.'
        : error instanceof Error ? error.message : 'Narration failed'
      this.onNotification?.(this.errorMessage, true)
    }
  }

  return (
    <div class={`narration-player ${this.compact ? 'compact' : ''}`}>
      <button
        type="button"
        attr:disabled={use(this.status).map((status: NarrationPlayerState['status']) => status === 'loading' || this.disabled === true)}
        aria-label={this.disabled ? 'Select a satellite to hear its narration' : 'Hear satellite narration'}
        on:click={play}
      >
        {this.compact
          ? <IconoirIcon svg={speakerIcon} />
          : use(this.status).map((status: NarrationPlayerState['status']) => {
          if (status === 'loading') return 'Generating voice...'
          if (status === 'playing') return 'Play again'
          return 'Hear the story'
          })}
      </button>
      {!this.compact && use(this.status).map((status: NarrationPlayerState['status']) => (
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

  :scope.compact {
    margin: 0;
  }

  :scope.compact button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 4px;
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
