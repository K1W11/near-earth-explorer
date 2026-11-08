import { css, type Component } from 'dreamland/core'
import earthDark from '../assets/pixelearth.png'
import { fetchActiveSatellites, type Satellite } from '../api/backend'
import { OrbitOverlay } from './OrbitOverlay'
import { SelectionTray } from './SelectionTray'
import { PromptDock } from './PromptDock'
import { NarrationLog } from './NarrationLog'

const satelliteAngle = (satellite: Satellite, index: number) => {
  let hash = index
  for (const character of satellite.name) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  }
  return hash % 360
}

// Measured from the solid globe pixels; the larger alpha bounds include the
// dithered halo and should not be used as the orbital surface.
const earthGlobeDiameter = 637 / 1041
const altitudeRuler = [400, 1_000, 2_000, 5_000, 10_000, 20_000, 36_000]
const orbitBands = [
  { name: 'LEO', from: 0, to: 2_000, color: 'rgb(65 170 255 / 10%)', edge: 'rgb(65 170 255 / 45%)' },
  { name: 'MEO', from: 2_000, to: 35_286, color: 'rgb(100 255 170 / 8%)', edge: 'rgb(100 255 170 / 40%)' },
  { name: 'GEO', from: 35_286, to: 36_286, color: 'rgb(255 210 80 / 14%)', edge: 'rgb(255 210 80 / 65%)' },
  { name: 'HEO', from: 36_286, to: Number.POSITIVE_INFINITY, color: 'rgb(255 110 150 / 9%)', edge: 'rgb(255 110 150 / 45%)' },
] as const
const geoAltitude = 35_786
const geoBandHalfWidth = 8
const orbitBandGap = 8
const selectionColor = '#62d9ff'

const orbitRadius = (
  altitude: number,
  earthRadius: number,
  maximumRadius: number,
  maximumAltitude: number,
) => {
  const altitudeProgress = Math.log1p(Math.max(0, altitude))
    / Math.log1p(Math.max(1, maximumAltitude))
  return earthRadius + (maximumRadius - earthRadius) * altitudeProgress
}

const drawOrbitBand = (
  context: CanvasRenderingContext2D,
  innerRadius: number,
  outerRadius: number,
  fillStyle: string,
  strokeStyle: string,
) => {
  context.beginPath()
  context.arc(0, 0, outerRadius, 0, Math.PI * 2)
  context.arc(0, 0, innerRadius, 0, Math.PI * 2, true)
  context.fillStyle = fillStyle
  context.fill('evenodd')
  context.beginPath()
  context.arc(0, 0, outerRadius, 0, Math.PI * 2)
  context.strokeStyle = strokeStyle
  context.stroke()
}

const drawBandLabel = (
  context: CanvasRenderingContext2D,
  name: string,
  angle: number,
  radius: number,
  color: string,
) => {
  const x = Math.sin(angle) * radius
  const y = -Math.cos(angle) * radius
  context.save()
  context.translate(x, y)
  context.rotate(angle)
  context.font = '600 9px system-ui, sans-serif'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  const paddingX = 3
  const paddingY = 2
  const metrics = context.measureText(name)
  const width = metrics.width + paddingX * 2
  const height = 9 + paddingY * 2
  const cornerRadius = 3
  context.beginPath()
  context.moveTo(-width / 2 + cornerRadius, -height / 2)
  context.lineTo(width / 2 - cornerRadius, -height / 2)
  context.quadraticCurveTo(width / 2, -height / 2, width / 2, -height / 2 + cornerRadius)
  context.lineTo(width / 2, height / 2 - cornerRadius)
  context.quadraticCurveTo(width / 2, height / 2, width / 2 - cornerRadius, height / 2)
  context.lineTo(-width / 2 + cornerRadius, height / 2)
  context.quadraticCurveTo(-width / 2, height / 2, -width / 2, height / 2 - cornerRadius)
  context.lineTo(-width / 2, -height / 2 + cornerRadius)
  context.quadraticCurveTo(-width / 2, -height / 2, -width / 2 + cornerRadius, -height / 2)
  context.closePath()
  context.fillStyle = 'rgb(0 0 0 / 88%)'
  context.fill()
  context.strokeStyle = color
  context.lineWidth = 1
  context.stroke()
  context.fillStyle = color
  context.fillText(name, 0, 0)
  context.restore()
}

type OrbitCanvasState = {
  canvas: HTMLCanvasElement
  satellites: Satellite[]
  status: 'loading' | 'ready' | 'error'
  errorMessage: string
  mode: 'rotate' | 'scroll'
  speed: number
  hoveredSatellite: number
  selectedSatellite: Satellite | null
  trayOpen: boolean
}

export const OrbitCanvas: Component<{}, OrbitCanvasState> = function () {
  this.satellites = []
  this.status = 'loading'
  this.errorMessage = ''
  this.mode = 'rotate'
  this.speed = 8
  this.hoveredSatellite = -1
  this.selectedSatellite = null
  this.trayOpen = false
  let addNarrationNotification = (_message: string, _error?: boolean, _stop?: () => void) => {}

  this.cx.mount = () => {
    const canvas = this.canvas
    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error('Unable to create a 2D context for the orbit visualization')
    }

    const earth = new Image()
    earth.src = earthDark
    let width = 0
    let height = 0
    let rotation = 0
    let rotationTarget: number | null = null
    let scrollVelocity = 0
    let previousTime = performance.now()
    let previousMode = this.mode
    let resizeTimer: number | undefined
    let resizeObserver: ResizeObserver
    let wheelListener: ((event: WheelEvent) => void) | undefined
    let pointerMoveListener: ((event: PointerEvent) => void) | undefined
    let pointerLeaveListener: (() => void) | undefined
    let clickListener: ((event: MouseEvent) => void) | undefined
    let pointerX = 0
    let pointerY = 0

    const resize = () => {
      const bounds = canvas.getBoundingClientRect()
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      width = bounds.width
      height = bounds.height
      canvas.width = Math.floor(width * pixelRatio)
      canvas.height = Math.floor(height * pixelRatio)
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
    }

    const draw = (time: number) => {
      if (!canvas.isConnected) {
        requestAnimationFrame(draw)
        return
      }
      const bounds = canvas.getBoundingClientRect()
      if (bounds.width !== width || bounds.height !== height) {
        resize()
      }

      const elapsed = Math.min((time - previousTime) / 1000, 0.05)
      previousTime = time
      if (this.mode !== previousMode) {
        scrollVelocity = 0
        if (this.mode === 'rotate') {
          this.selectedSatellite = null
          this.trayOpen = false
        }
        previousMode = this.mode
      }
      if (this.mode === 'rotate') {
        rotation += elapsed * this.speed
      } else {
        rotation += scrollVelocity * elapsed
        scrollVelocity *= Math.exp(-elapsed * 8)
        if (rotationTarget !== null) {
          const distance = rotationTarget - rotation
          rotation += distance * (1 - Math.exp(-elapsed * 6))
          if (Math.abs(distance) < 0.05) {
            rotation = rotationTarget
            rotationTarget = null
          }
        }
      }
      if (pointerX || pointerY) {
        this.hoveredSatellite = satelliteAtPoint(pointerX, pointerY)
      }
      context.clearRect(0, 0, width, height)

      if (width > 0 && height > 0) {
        const centerX = width / 2
        const centerY = height
        const altitudes = this.satellites.map((satellite) => satellite.altitude_km ?? 0)
        const earthWidth = Math.min(650, width * 0.72)
        const earthRadius = earthWidth * earthGlobeDiameter / 2
        const maximumAltitude = Math.max(36_000, ...altitudes)
        const maximumRadius = Math.min(width * 0.46, height * 0.92)

        context.save()
        context.translate(centerX, centerY)
        context.rotate((rotation % 360) * Math.PI / 180)

        context.strokeStyle = 'rgb(255 255 255 / 18%)'
        context.lineWidth = 1
        for (const altitude of altitudeRuler) {
          if (altitude > maximumAltitude) continue
          context.beginPath()
          context.arc(
            0,
            0,
            orbitRadius(altitude, earthRadius, maximumRadius, maximumAltitude),
            0,
            Math.PI * 2,
          )
          context.stroke()
        }

        let previousBandOuter = earthRadius
        for (const band of orbitBands) {
          if (band.from > maximumAltitude) continue
          let innerRadius = orbitRadius(
            Math.min(band.from, maximumAltitude),
            earthRadius,
            maximumRadius,
            maximumAltitude,
          )
          let outerRadius = Math.min(
            maximumRadius,
            orbitRadius(
              Math.min(band.to, maximumAltitude),
              earthRadius,
              maximumRadius,
              maximumAltitude,
            ),
          )
          if (band.name === 'GEO') {
            innerRadius = orbitRadius(
              geoAltitude - geoBandHalfWidth,
              earthRadius,
              maximumRadius,
              maximumAltitude,
            )
            outerRadius = orbitRadius(
              geoAltitude + geoBandHalfWidth,
              earthRadius,
              maximumRadius,
              maximumAltitude,
            )
          }
          if (band.name === 'HEO') {
            innerRadius = previousBandOuter
          }
          if (outerRadius <= innerRadius) continue
          drawOrbitBand(context, innerRadius, outerRadius, band.color, band.edge)
          previousBandOuter = outerRadius

          const labelInnerRadius = band.name === 'HEO'
            ? Math.min(maximumRadius, innerRadius + orbitBandGap)
            : innerRadius
          const labelRadius = (labelInnerRadius + outerRadius) / 2
          for (const labelAngle of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) {
            drawBandLabel(context, band.name, labelAngle, labelRadius, band.edge)
          }
        }

        for (const [index, satellite] of this.satellites.entries()) {
          const angle = satelliteAngle(satellite, index) * Math.PI / 180
          const radius = orbitRadius(
            satellite.altitude_km ?? 0,
            earthRadius,
            maximumRadius,
            maximumAltitude,
          )
          const x = Math.sin(angle) * radius
          const y = -Math.cos(angle) * radius
          const isHovered = index === this.hoveredSatellite
          const isSelected = this.selectedSatellite?.name === satellite.name
          context.beginPath()
          context.arc(x, y, isHovered || isSelected ? 5 : 2.5, 0, Math.PI * 2)
          context.fillStyle = isSelected ? selectionColor : 'white'
          context.shadowColor = isSelected
            ? selectionColor
            : 'rgb(180 220 255 / 80%)'
          context.shadowBlur = isHovered || isSelected ? 12 : 7
          context.fill()
        }

        if (earth.complete && earth.naturalWidth > 0) {
          const earthHeight = earthWidth * earth.naturalHeight / earth.naturalWidth
          context.shadowColor = 'transparent'
          context.shadowBlur = 0
          context.imageSmoothingEnabled = false
          context.drawImage(earth, -earthWidth / 2, -earthHeight / 2, earthWidth, earthHeight)
        }
        context.restore()
      }

      requestAnimationFrame(draw)
    }

    const handleResize = () => {
      if (resizeTimer !== undefined) window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        resizeTimer = undefined
        resize()
      }, 150)
    }

    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(canvas)
    wheelListener = (event) => {
      if (this.mode === 'rotate') {
        this.mode = 'scroll'
        scrollVelocity = 0
        rotationTarget = null
        event.preventDefault()
        return
      }
      event.preventDefault()
      rotationTarget = null
      const delta = event.deltaY * 0.018
      rotation += delta
      scrollVelocity += delta * 30
    }
    const satelliteAtPoint = (clientX: number, clientY: number) => {
      if (width === 0 || height === 0 || this.satellites.length === 0) return -1
      const bounds = canvas.getBoundingClientRect()
      const localX = clientX - bounds.left - width / 2
      const localY = clientY - bounds.top - height
      const rotationRadians = -(rotation % 360) * Math.PI / 180
      const x = localX * Math.cos(rotationRadians) - localY * Math.sin(rotationRadians)
      const y = localX * Math.sin(rotationRadians) + localY * Math.cos(rotationRadians)
      const altitudes = this.satellites.map((satellite) => satellite.altitude_km ?? 0)
      const maximumAltitude = Math.max(36_000, ...altitudes)
      const earthWidth = Math.min(650, width * 0.72)
      const earthRadius = earthWidth * earthGlobeDiameter / 2
      const maximumRadius = Math.min(width * 0.46, height * 0.92)
      let closest = -1
      const hitRadius = this.mode === 'rotate' ? 24 : 16
      let closestDistance = hitRadius
      for (const [index, satellite] of this.satellites.entries()) {
        const angle = satelliteAngle(satellite, index) * Math.PI / 180
        const radius = orbitRadius(satellite.altitude_km ?? 0, earthRadius, maximumRadius, maximumAltitude)
        const satelliteX = Math.sin(angle) * radius
        const satelliteY = -Math.cos(angle) * radius
        const distance = Math.hypot(x - satelliteX, y - satelliteY)
        if (distance < closestDistance) {
          closest = index
          closestDistance = distance
        }
      }
      return closest
    }
    pointerMoveListener = (event) => {
      pointerX = event.clientX
      pointerY = event.clientY
      this.hoveredSatellite = satelliteAtPoint(pointerX, pointerY)
    }
    pointerLeaveListener = () => {
      pointerX = 0
      pointerY = 0
      this.hoveredSatellite = -1
    }
    clickListener = (event) => {
      const index = satelliteAtPoint(event.clientX, event.clientY)
      if (index < 0) {
        this.selectedSatellite = null
        this.trayOpen = false
        return
      }
      this.mode = 'scroll'
      scrollVelocity = 0
      const name = this.satellites[index].name
      const isDeselecting = this.selectedSatellite?.name === name
      this.selectedSatellite = isDeselecting ? null : this.satellites[index]
      this.trayOpen = !isDeselecting
      if (isDeselecting) {
        rotationTarget = null
      } else {
        const desiredRotation = -satelliteAngle(this.satellites[index], index)
        const turns = Math.round((rotation - desiredRotation) / 360)
        rotationTarget = desiredRotation + turns * 360
      }
    }
    canvas.addEventListener('wheel', wheelListener, { passive: false })
    canvas.addEventListener('pointermove', pointerMoveListener)
    canvas.addEventListener('pointerleave', pointerLeaveListener)
    canvas.addEventListener('click', clickListener)
    resize()
    requestAnimationFrame(draw)

    const loadSatellites = async () => {
      try {
        const response = await fetchActiveSatellites(500)
        if (canvas.isConnected) {
          this.satellites = response.satellites
          this.status = 'ready'
        }
      } catch (error: unknown) {
        if (canvas.isConnected) {
          this.errorMessage = error instanceof Error ? error.message : 'Unable to load satellites'
          this.status = 'error'
        }
      }
    }

    void loadSatellites()
  }

  return (
    <section class="view app-view">
      <div class="app-layout">
        <div class="left-column">
          <OrbitOverlay
            status={use(this.status)}
            errorMessage={use(this.errorMessage)}
            satellites={use(this.satellites)}
            mode={use(this.mode)}
            selectedSatellite={use(this.selectedSatellite)}
            onNarration={(message, error, stop) => addNarrationNotification(message, error, stop)}
            onRotateToggle={() => {
              this.mode = this.mode === 'rotate' ? 'scroll' : 'rotate'
              if (this.mode === 'rotate') {
                this.selectedSatellite = null
                this.trayOpen = false
              }
            }}
          />
          <SelectionTray
            selectedSatellite={use(this.selectedSatellite)}
            trayOpen={use(this.trayOpen)}
            onNarration={(message, error, stop) => addNarrationNotification(message, error, stop)}
            onToggle={() => { this.trayOpen = !this.trayOpen }}
          />
        </div>
        <div class="conversation-column">
          <PromptDock
            selectedSatellite={use(this.selectedSatellite)}
            onNarration={(message, error, stop) => addNarrationNotification(message, error, stop)}
          />
        </div>
        <NarrationLog onReady={(add) => { addNarrationNotification = add }} />
      </div>
      <canvas
        class="orbit-canvas"
        this={use(this.canvas)}
        aria-label="Active satellites in orbit"
      ></canvas>
    </section>
  )
}

OrbitCanvas.style = css`
  :scope {
    position: relative;
    --layout-gap: 16px;
    overflow: hidden;
    height: 100%;
    box-sizing: border-box;
    padding: 24px 0;
    align-items: stretch;
    color: white;
    background: rgb(0 0 0 / 28%);
  }

  :scope .app-layout {
    position: absolute;
    inset: 24px 0;
    display: flex;
    min-height: 0;
    gap: var(--layout-gap);
  }

  :scope .left-column {
    display: flex;
    flex: 0 0 320px;
    width: 320px;
    max-width: 85vw;
    flex-direction: column;
    min-height: 0;
    gap: var(--layout-gap);
  }

  :scope .conversation-column {
    pointer-events: none;
    display: flex;
    flex: 1 1 0;
    min-width: 0;
    min-height: 0;
    z-index: 3;
  }

  :scope .orbit-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: auto;
  }

  :scope .orbit-controls {
    display: none;
    gap: 12px;
    align-items: end;
    margin: 16px 0;
    padding: 0;
    border: 0;
  }

  :scope .orbit-controls label {
    display: grid;
    gap: 4px;
    font-size: 12px;
  }

  :scope .orbit-controls select,
  :scope .orbit-controls input {
    min-width: 100px;
  }
`
