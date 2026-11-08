import { css, type Component } from 'dreamland/core'
import { fetchSatelliteOverview, type Satellite, type SatelliteOverview } from '../api/backend'
import { NarrationPlayer } from './NarrationPlayer'

type SelectionTrayProps = {
  selectedSatellite: Satellite | null
  trayOpen: boolean
  onToggle: () => void
  onNarration: (message: string, error?: boolean, stop?: () => void) => void
}

const formatDegrees = (value: number | null) => value === null ? 'No info' : `${value.toFixed(2)}°`
const formatDuration = (minutes: number | null) => minutes === null ? 'No info' : (
  minutes >= 60
    ? `${Math.floor(minutes / 60)} h ${Math.round(minutes % 60)} min`
    : `${minutes.toFixed(1)} min`
)
export const SelectionTray: Component<SelectionTrayProps, { overview: SatelliteOverview | null; overviewFailed: boolean }> = function () {
  this.overview = null as SatelliteOverview | null
  this.overviewFailed = false
  use(this.selectedSatellite).listen((satellite) => {
    this.overview = null
    this.overviewFailed = false
    if (satellite) {
      void fetchSatelliteOverview(satellite.name).then((overview) => {
        if (this.selectedSatellite?.name === satellite.name) this.overview = overview
      }).catch((error: unknown) => {
        if (this.selectedSatellite?.name !== satellite.name) return
        this.overviewFailed = true
        console.warn('Satellite overview unavailable', error)
      })
    }
  })

  return (
    <aside class={use(this.trayOpen).map((open) => `selection-tray ${open ? 'is-open' : 'is-closed'}`)} aria-label="Selected satellite">
      <button class="tray-toggle" type="button" aria-expanded={use(this.trayOpen)} on:click={this.onToggle}>
        {use(this.trayOpen).map((open) => open ? '‹' : '›')}
      </button>
      <div class="tray-content">
        {use(this.selectedSatellite).map((satellite: Satellite | null) => satellite
          ? use(this.overview).map((overview: SatelliteOverview | null) => overview
            ? (
              <article class="selected-satellite">
                <header>
                  <strong>{satellite.name}</strong>
                  <span>{overview.orbit_class} · {overview.orbit_description}</span>
                </header>
                <section class="satellite-details">
                  <div class="category-heading">
                    <h3>Overview</h3>
                    <NarrationPlayer name={satellite.name} type="satellite" category="overview" compact onNotification={this.onNarration} />
                  </div>
                  <dl>
                    <dt>Altitude</dt>
                    <dd>{overview.altitude_km === null ? 'No info' : `${overview.altitude_km.toLocaleString(undefined, { maximumFractionDigits: 1 })} km`}</dd>
                    <dt>Orbit type</dt>
                    <dd>{overview.orbit_class} · {overview.orbit_description}</dd>
                    <dt>Orbital period</dt>
                    <dd>{formatDuration(overview.orbital_period_minutes)}</dd>
                    <dt>Inclination</dt>
                    <dd>{formatDegrees(overview.inclination_degrees)} from the equator</dd>
                    <dt>Eccentricity</dt>
                    <dd>{overview.eccentricity === null ? 'No info' : `${overview.eccentricity.toFixed(7)} · ${overview.eccentricity < 0.01 ? 'nearly circular' : 'elliptical'}`}</dd>
                  </dl>
                </section>
                <section class="satellite-details">
                    <div class="category-heading">
                      <h3>Orbital position</h3>
                      <NarrationPlayer name={satellite.name} type="satellite" category="orbital_position" compact onNotification={this.onNarration} />
                    </div>
                    <dl>
                      <dt>Right ascension of ascending node</dt>
                      <dd>{formatDegrees(overview.right_ascension_ascending_node_degrees)}</dd>
                      <dt>Argument of perigee</dt>
                      <dd>{formatDegrees(overview.argument_of_perigee_degrees)}</dd>
                      <dt>Mean anomaly</dt>
                      <dd>{formatDegrees(overview.mean_anomaly_degrees)}</dd>
                      <dt>Mean motion</dt>
                      <dd>{overview.mean_motion_revolutions_per_day === null ? 'No info' : `${overview.mean_motion_revolutions_per_day.toFixed(8)} revolutions/day`}</dd>
                    </dl>
                  </section>
                <details>
                      <summary>Tracking record</summary>
                      <NarrationPlayer name={satellite.name} type="satellite" category="tracking" compact onNotification={this.onNarration} />
                    <dl>
                      <dt>NORAD catalog number</dt>
                      <dd>{overview.norad_catalog_number} ({overview.classification})</dd>
                      <dt>International designator</dt>
                      <dd>{overview.international_designator || 'Not available'}</dd>
                      <dt>Elements epoch</dt>
                      <dd>{overview.elements_epoch}</dd>
                      <dt>Revolutions at epoch</dt>
                      <dd>{overview.revolutions_at_epoch}</dd>
                    </dl>
                  </details>
                <details>
                  <summary>Raw two-line element set</summary>
                  <code>{overview.tle1}</code>
                  <code>{overview.tle2}</code>
                </details>
              </article>
              )
              : use(this.overviewFailed).map((failed) => (
                <p class="tray-empty">{failed ? 'Satellite details unavailable' : 'Loading satellite overview...'}</p>
              ))
            )
          : <p class="tray-empty">No satellite selected</p>
        )}
      </div>
    </aside>
  )
}

SelectionTray.style = css`
  :scope {
    display: flex;
    flex: 1 1 auto;
    flex-direction: row;
    align-self: stretch;
    width: 100%;
    max-width: 85vw;
    min-height: 0;
    overflow: hidden;
    border: 1px solid rgb(255 255 255 / 25%);
    border-left: 0;
    border-radius: 0 6px 6px 0;
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
    transition: width 180ms ease;
    z-index: 2;
  }

  :scope.is-closed {
    width: 24px;
    pointer-events: none;
  }

  :scope .tray-content {
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    padding: 16px 0 16px 16px;
    scrollbar-width: none;
  }

  :scope .tray-content::-webkit-scrollbar {
    display: none;
  }

  :scope.is-closed .tray-content {
    display: none;
  }

  :scope .tray-toggle {
    order: 2;
    flex: 0 0 24px;
    align-self: center;
    width: 24px;
    height: 56px;
    padding: 0;
    border: 0;
    color: white;
    cursor: pointer;
    background: transparent;
    pointer-events: auto;
  }

  :scope .selected-satellite {
    display: flex;
    flex-direction: column;
    gap: var(--layout-gap);
    min-height: 100%;
    padding: 0 16px 0 8px;
    border-left: 3px solid #62d9ff;
  }

  :scope .selected-satellite header,
  :scope .satellite-details {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  :scope .selected-satellite header span,
  :scope .satellite-details h3,
  :scope .satellite-details dt,
  :scope details dt,
  :scope .tray-empty {
    color: rgb(255 255 255 / 70%);
    font-size: 11px;
  }

  :scope .selected-satellite header strong {
    color: rgb(255 255 255 / 90%);
    font-size: 13px;
    letter-spacing: 0.04em;
  }

  :scope .category-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 32px;
  }

  :scope .category-heading h3 {
    margin: 0;
    font-size: 12px;
    color: rgb(255 255 255 / 90%);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  :scope summary .narration-player {
    display: none;
  }

  :scope .category-heading .narration-player,
  :scope details > .narration-player {
    margin-left: auto;
    flex: 0 0 auto;
  }

  :scope summary {
    min-height: 32px;
    padding: 8px 32px 8px 2px;
    box-sizing: border-box;
    color: rgb(255 255 255 / 90%);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    line-height: 1.3;
    text-transform: uppercase;
    cursor: pointer;
  }

  :scope .satellite-details dl,
  :scope details dl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 10px;
    margin: 0;
  }

  :scope .satellite-details dd,
  :scope details dd {
    margin: 0;
    text-align: right;
    font-size: 11px;
  }

  :scope details {
    position: relative;
    min-width: 0;
  }

  :scope summary::marker {
    color: rgb(255 255 255 / 70%);
  }

  :scope details > .narration-player {
    position: absolute;
    top: 4px;
    right: 0;
  }

  :scope details code {
    display: block;
    overflow-wrap: anywhere;
    margin-top: 6px;
    color: rgb(255 255 255 / 58%);
    font: 10px/1.35 ui-monospace, monospace;
  }
`
