import { css, type Component } from 'dreamland/core'
import type { Satellite } from '../api/backend'

type SelectionTrayProps = {
  selectedSatellite: Satellite | null
  trayOpen: boolean
  onToggle: () => void
}

type ParsedTle = {
  satelliteNumber: string
  classification: string
  internationalDesignator: string
  epoch: string
  inclination: number
  raan: number
  eccentricity: number
  argumentOfPerigee: number
  meanAnomaly: number
  meanMotion: number
  periodMinutes: number
  revolutionNumber: string
}

const parseTle = (line1: string, line2: string): ParsedTle | null => {
  if (line1.length < 68 || line2.length < 68) return null
  const inclination = Number(line2.slice(8, 16))
  const raan = Number(line2.slice(17, 25))
  const eccentricity = Number(`0.${line2.slice(26, 33)}`)
  const argumentOfPerigee = Number(line2.slice(34, 42))
  const meanAnomaly = Number(line2.slice(43, 51))
  const meanMotion = Number(line2.slice(52, 63))
  if (![inclination, raan, eccentricity, argumentOfPerigee, meanAnomaly, meanMotion].every(Number.isFinite)) {
    return null
  }

  const epochYear = Number(line1.slice(18, 20))
  const epochDay = Number(line1.slice(20, 32))
  const epochDate = Number.isFinite(epochYear) && Number.isFinite(epochDay)
    ? new Date(Date.UTC(epochYear + (epochYear < 57 ? 2000 : 1900), 0, 1) + (epochDay - 1) * 86_400_000)
    : null

  return {
    satelliteNumber: line1.slice(2, 7).trim(),
    classification: line1.slice(7, 8),
    internationalDesignator: line1.slice(9, 17).trim(),
    epoch: epochDate && !Number.isNaN(epochDate.valueOf())
      ? epochDate.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
      : 'Unknown',
    inclination,
    raan,
    eccentricity,
    argumentOfPerigee,
    meanAnomaly,
    meanMotion,
    periodMinutes: 1440 / meanMotion,
    revolutionNumber: line2.slice(63, 68).trim(),
  }
}

const formatDegrees = (value: number) => `${value.toFixed(2)}°`
const formatDuration = (minutes: number) => (
  minutes >= 60
    ? `${Math.floor(minutes / 60)} h ${Math.round(minutes % 60)} min`
    : `${minutes.toFixed(1)} min`
)
const orbitClass = (altitude: number) => (
  altitude < 2_000 ? 'LEO' : altitude < 35_286 ? 'MEO' : altitude < 36_286 ? 'GEO' : 'HEO'
)
const orbitDescription = (altitude: number) => {
  const type = orbitClass(altitude)
  return type === 'LEO' ? 'Low Earth orbit'
    : type === 'MEO' ? 'Medium Earth orbit'
      : type === 'GEO' ? 'Geostationary region'
        : 'Highly elliptical orbit'
}

export const SelectionTray: Component<SelectionTrayProps> = function () {
  return (
    <aside class={use`selection-tray ${use(this.trayOpen).map((open) => open ? 'is-open' : 'is-closed')}`} aria-label="Selected satellite">
      <button class="tray-toggle" type="button" aria-expanded={use(this.trayOpen)} on:click={this.onToggle}>
        {use(this.trayOpen).map((open) => open ? '‹' : '›')}
      </button>
      <div class="tray-content">
        {use(this.selectedSatellite).map((satellite: Satellite | null) => satellite
          ? (() => {
            const tle = parseTle(satellite.tle1, satellite.tle2)
            return (
              <article class="selected-satellite">
                <header>
                  <strong>{satellite.name}</strong>
                  <span>{orbitClass(satellite.altitude_km)} · {orbitDescription(satellite.altitude_km)}</span>
                </header>
                <section class="satellite-details">
                  <h3>Overview</h3>
                  <dl>
                    <dt>Altitude</dt>
                    <dd>{satellite.altitude_km.toLocaleString(undefined, { maximumFractionDigits: 1 })} km</dd>
                    <dt>Orbit type</dt>
                    <dd>{orbitClass(satellite.altitude_km)} · {orbitDescription(satellite.altitude_km)}</dd>
                    {tle && (
                      <>
                        <dt>Orbital period</dt>
                        <dd>{formatDuration(tle.periodMinutes)}</dd>
                        <dt>Inclination</dt>
                        <dd>{formatDegrees(tle.inclination)} from the equator</dd>
                        <dt>Eccentricity</dt>
                        <dd>{tle.eccentricity.toFixed(7)} · {tle.eccentricity < 0.01 ? 'nearly circular' : 'elliptical'}</dd>
                      </>
                    )}
                  </dl>
                </section>
                {tle && (
                  <section class="satellite-details">
                    <h3>Orbital position</h3>
                    <dl>
                      <dt>Right ascension of ascending node</dt>
                      <dd>{formatDegrees(tle.raan)}</dd>
                      <dt>Argument of perigee</dt>
                      <dd>{formatDegrees(tle.argumentOfPerigee)}</dd>
                      <dt>Mean anomaly</dt>
                      <dd>{formatDegrees(tle.meanAnomaly)}</dd>
                      <dt>Mean motion</dt>
                      <dd>{tle.meanMotion.toFixed(8)} revolutions/day</dd>
                    </dl>
                  </section>
                )}
                {tle && (
                  <details>
                    <summary>Tracking record</summary>
                    <dl>
                      <dt>NORAD catalog number</dt>
                      <dd>{tle.satelliteNumber} ({tle.classification})</dd>
                      <dt>International designator</dt>
                      <dd>{tle.internationalDesignator || 'Not available'}</dd>
                      <dt>Elements epoch</dt>
                      <dd>{tle.epoch}</dd>
                      <dt>Revolutions at epoch</dt>
                      <dd>{tle.revolutionNumber}</dd>
                    </dl>
                  </details>
                )}
                <details>
                  <summary>Raw two-line element set</summary>
                  <code>{satellite.tle1}</code>
                  <code>{satellite.tle2}</code>
                </details>
              </article>
            )
          })()
          : <p class="tray-empty">No satellite selected</p>
        )}
      </div>
    </aside>
  )
}

SelectionTray.style = css`
  :scope {
    flex: 1 1 auto;
    align-self: flex-start;
    z-index: 2;
    display: flex;
    width: 320px;
    max-width: 85vw;
    min-height: 0;
    transition: width 180ms ease;
    border: 1px solid rgb(255 255 255 / 25%);
    border-left: 0;
    border-radius: 0 6px 6px 0;
  }

  :scope.is-closed {
    width: 24px;
  }

  :scope .tray-content {
    flex: 1;
    display: grid;
    gap: 12px;
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
    margin: 0;
    color: rgb(255 255 255 / 90%);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
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
