import { css, type Component } from 'dreamland/core'
import earthDark from '../assets/pixelearth.png'
import { fetchActiveSatellites, type Satellite } from '../api/backend'

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

type OrbitCanvasState = {
  canvas: HTMLCanvasElement
  satellites: Satellite[]
  status: 'loading' | 'ready' | 'error'
  errorMessage: string
}

export const AppView: Component<{}, OrbitCanvasState> = function () {
  this.satellites = []
  this.status = 'loading'
  this.errorMessage = ''

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
    let previousTime = performance.now()
    let frame = 0
    let resizeTimer: number | undefined
    let resizeObserver: ResizeObserver

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
        cancelAnimationFrame(frame)
        resizeObserver.disconnect()
        if (resizeTimer !== undefined) window.clearTimeout(resizeTimer)
        context.clearRect(0, 0, width, height)
        return
      }

      const elapsed = Math.min((time - previousTime) / 1000, 0.05)
      previousTime = time
      rotation = (rotation + elapsed * 8) % 360
      context.clearRect(0, 0, width, height)

      if (width > 0 && height > 0) {
        const centerX = width / 2
        const centerY = height
        const altitudes = this.satellites.map((satellite) => satellite.altitude_km)
        const earthWidth = Math.min(650, width * 0.72)
        const earthRadius = earthWidth * earthGlobeDiameter / 2
        const maximumAltitude = Math.max(36_000, ...altitudes)
        const maximumRadius = Math.min(width * 0.46, height * 0.92)

        context.save()
        context.translate(centerX, centerY)
        context.rotate(rotation * Math.PI / 180)

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

        for (const [index, satellite] of this.satellites.entries()) {
          const angle = satelliteAngle(satellite, index) * Math.PI / 180
          const radius = orbitRadius(
            satellite.altitude_km,
            earthRadius,
            maximumRadius,
            maximumAltitude,
          )
          const x = Math.sin(angle) * radius
          const y = -Math.cos(angle) * radius
          context.beginPath()
          context.arc(x, y, 2.5, 0, Math.PI * 2)
          context.fillStyle = 'white'
          context.shadowColor = 'rgb(180 220 255 / 80%)'
          context.shadowBlur = 7
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

      frame = requestAnimationFrame(draw)
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
    resize()
    frame = requestAnimationFrame(draw)

    const loadSatellites = async () => {
      try {
        const response = await fetchActiveSatellites(100)
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
      <section class="satellite-list" aria-live="polite">
        <h1>Active satellites</h1>
        {use(this.status).map((status) => {
          if (status === 'loading') return <p>Loading satellites...</p>
          if (status === 'error') return <p role="alert">{use(this.errorMessage)}</p>
          return <p>{use(this.satellites).map((satellites) => `${satellites.length} satellites in orbit`)}</p>
        })}
      </section>
      <canvas
        class="orbit-canvas"
        this={use(this.canvas)}
        aria-label="Active satellites in orbit"
      ></canvas>
    </section>
  )
}

AppView.style = css`
  :scope {
    position: relative;
    overflow: hidden;
    padding: 48px 24px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    min-height: 100%;
    color: white;
  }

  :scope .orbit-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  :scope .satellite-list {
    position: relative;
    z-index: 1;
    align-self: flex-start;
    width: min(100%, 420px);
    padding: 24px;
    border: 1px solid rgb(255 255 255 / 20%);
    background: rgb(0 0 0 / 60%);
  }

  :scope .satellite-list h1 {
    margin: 0;
  }
`
