import { css, type Component } from 'dreamland/core'
import type { Satellite } from '../api/backend'
import playIcon from 'iconoir/icons/regular/play.svg?raw'
import pauseIcon from 'iconoir/icons/regular/pause.svg?raw'
import speakerIcon from 'iconoir/icons/regular/sound-high.svg?raw'
import { IconoirIcon } from './IconoirIcon'
import { NarrationPlayer } from './NarrationPlayer'

type OrbitOverlayProps = {
  status: 'loading' | 'ready' | 'error'
  errorMessage: string
  satellites: Satellite[]
  mode: 'rotate' | 'scroll'
  selectedSatellite: Satellite | null
  onNarration: (message: string, error?: boolean, stop?: () => void) => void
  onRotateToggle: () => void
}

export const OrbitOverlay: Component<OrbitOverlayProps> = function () {
  return (
    <div class="orbit-overlay">
      <section class="satellite-list" aria-live="polite">
        {use(this.status).map((status) => {
          if (status === 'loading') return <p>Loading satellites...</p>
          if (status === 'error') return <p role="alert">{use(this.errorMessage)}</p>
          return <p>{use(this.satellites).map((satellites) => `${satellites.length} satellites`)}</p>
        })}
      </section>
      <div class="overlay-actions">
        {use(this.selectedSatellite).map((satellite) => satellite
          ? <NarrationPlayer name={satellite.name} type="satellite" compact onNotification={this.onNarration} />
          : (
            <button
              class="narration-placeholder"
              type="button"
              disabled
              aria-label="Select a satellite to hear its narration"
              title="Select a satellite to hear its narration"
            >
              <IconoirIcon svg={speakerIcon} />
            </button>
          )
        )}
        <button
          class="rotate-toggle"
          type="button"
          aria-label={use(this.mode).map((mode) => mode === 'rotate' ? 'Rotation is on; pause rotation' : 'Rotation is off; resume rotation')}
          title={use(this.mode).map((mode) => mode === 'rotate' ? 'Rotation on' : 'Rotation off')}
          on:click={this.onRotateToggle}
        >
          {use(this.mode).map((mode) => (
            <IconoirIcon
              svg={mode === 'rotate' ? pauseIcon : playIcon}
              label={mode === 'rotate' ? 'Pause rotation' : 'Start rotation'}
            />
          ))}
        </button>
      </div>
    </div>
  )
}

OrbitOverlay.style = css`
  :scope {
    flex: 0 0 32px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    width: 100%;
    box-sizing: border-box;
    padding: 0 24px;
    z-index: 3;
    pointer-events: none;
  }

  :scope .satellite-list {
    width: auto;
    padding: 8px 12px;
    border: 1px solid rgb(255 255 255 / 20%);
    border-radius: 4px;
    background: rgb(0 0 0 / 72%);
    box-shadow: 0 4px 16px rgb(0 0 0 / 25%);
    color: rgb(255 255 255 / 85%);
    font: 500 12px/1.3 system-ui, sans-serif;
    pointer-events: auto;
  }

  :scope .satellite-list p {
    margin: 0;
  }

  :scope .rotate-toggle {
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid rgb(255 255 255 / 35%);
    border-radius: 4px;
    background: rgb(0 0 0 / 72%);
    box-shadow: 0 4px 16px rgb(0 0 0 / 25%);
    color: white;
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
    pointer-events: auto;
  }

  :scope .overlay-actions {
    display: flex;
    gap: 6px;
    pointer-events: auto;
  }

  :scope .narration-placeholder {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid rgb(255 255 255 / 35%);
    border-radius: 4px;
    background: rgb(0 0 0 / 72%);
    color: white;
    cursor: not-allowed;
    opacity: 0.55;
  }

  :scope .rotate-toggle:hover,
  :scope .rotate-toggle:focus-visible {
    background: rgb(255 255 255 / 22%);
  }
`
