import { css, type Component } from 'dreamland/core'
import { fetchSatelliteOverview, type Satellite, type SatelliteOverview } from '../api/backend'
import { NarrationPlayer } from './NarrationPlayer'

type SelectionTrayProps = {
  selectedSatellite: Satellite | null
  trayOpen: boolean
  onToggle: () => void
  onNarration: (message: string, error?: boolean, stop?: () => void) => void
}

const formatDegrees = (value: number) => `${value.toFixed(2)}°`
const formatDuration = (minutes: number) => (
  minutes >= 60
    ? `${Math.floor(minutes / 60)} h ${Math.round(minutes % 60)} min`
    : `${minutes.toFixed(1)} min`
)
export const SelectionTray: Component<SelectionTrayProps, { overview: SatelliteOverview | null }> = function () {
  this.overview = null as SatelliteOverview | null
  use(this.selectedSatellite).listen((satellite) => {
    this.overview = null
    if (satellite) {
      void fetchSatelliteOverview(satellite.name).then((overview) => {
        if (this.selectedSatellite?.name === satellite.name) this.overview = overview
      })
    }
  })

  return (
    <aside class={use`selection-tray ${use(this.trayOpen).map((open) => open ? 'is-open' : 'is-closed')}`} aria-label="Selected satellite">
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
                  <h3>Overview <NarrationPlayer name={satellite.name} type="satellite" category="overview" compact onNotification={this.onNarration} /></h3>
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
                    <dd>{overview.eccentricity.toFixed(7)} · {overview.eccentricity < 0.01 ? 'nearly circular' : 'elliptical'}</dd>
                  </dl>
                </section>
                <section class="satellite-details">
                    <h3>Orbital position <NarrationPlayer name={satellite.name} type="satellite" category="orbital_position" compact onNotification={this.onNarration} /></h3>
                    <dl>
                      <dt>Right ascension of ascending node</dt>
                      <dd>{formatDegrees(overview.right_ascension_ascending_node_degrees)}</dd>
                      <dt>Argument of perigee</dt>
                      <dd>{formatDegrees(overview.argument_of_perigee_degrees)}</dd>
                      <dt>Mean anomaly</dt>
                      <dd>{formatDegrees(overview.mean_anomaly_degrees)}</dd>
                      <dt>Mean motion</dt>
                      <dd>{overview.mean_motion_revolutions_per_day.toFixed(8)} revolutions/day</dd>
                    </dl>
                  </section>
                <details>
                    <summary>Tracking record <NarrationPlayer name={satellite.name} type="satellite" category="tracking" compact onNotification={this.onNarration} /></summary>
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
              : <p class="tray-empty">Loading satellite overview...</p>
            )
          : <p class="tray-empty">No satellite selected</p>
        )}
      </div>
    </aside>
  )
}

SelectionTray.style = css`
  :scope {
    flex: 0 0 320px;
    align-self: stretch;
    z-index: 2;
    display: flex;
    width: 320px;
    max-width: 85vw;
    min-height: 0;
    transition: flex-basis 180ms ease, width 180ms ease;
    border: 1px solid rgb(255 255 255 / 25%);
    border-left: 0;
    border-radius: 0 6px 6px 0;
  }

  :scope.is-closed {
    flex-basis: 24px;
    width: 24px;
  }

  :scope .tray-content {
    flex: 1;
    display: grid;
    gap: var(--layout-gap);
    overflow-y: auto;
    padding: 16px;
    padding-left: 0;
    
    background: rgb(0 0 0 / 78%);
    box-shadow: 4px 8px 20px rgb(0 0 0 / 30%);
  }

  :scope.is-closed .tray-content {
    display: none;
  }

  :scope .tray-toggle {
    align-self: center;
    width: 24px;
    height: 56px;
    padding: 0;
    border: 0;
    background: rgb(0 0 0 / 78%);
    color: white;
    cursor: pointer;
  }

  :scope .selected-satellite {
    display: grid;
    gap: 14px;
    padding-left: 8px;
    border-left: 3px solid #62d9ff;
  }

  :scope .selected-satellite header,
  :scope .satellite-details {
    display: grid;
    gap: 5px;
  }

  :scope .selected-satellite header span,
  :scope .satellite-details h3,
  :scope .satellite-details dt,
  :scope .selected-satellite details dt,
  :scope .tray-empty {
    color: rgb(255 255 255 / 70%);
    font-size: 11px;
  }

  :scope .satellite-details h3 {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 0;
    color: rgb(255 255 255 / 90%);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  :scope .satellite-details h3 .narration-player,
  :scope summary .narration-player {
    flex: 0 0 auto;
  }

  :scope summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  :scope .satellite-details dl,
  :scope .selected-satellite details dl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 5px 10px;
    margin: 0;
  }

  :scope .satellite-details dd,
  :scope .selected-satellite details dd {
    margin: 0;
    text-align: right;
    font-size: 11px;
  }

  :scope .selected-satellite details {
    display: grid;
    gap: 8px;
  }

  :scope summary {
    margin-bottom: 2px;
    color: rgb(255 255 255 / 82%);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    cursor: pointer;
  }

  :scope .selected-satellite code {
    display: block;
    overflow-wrap: anywhere;
    color: rgb(255 255 255 / 58%);
    font: 10px/1.35 ui-monospace, monospace;
  }
`
