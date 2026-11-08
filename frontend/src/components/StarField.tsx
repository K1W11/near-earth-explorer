import { css, type Component, type Delegate } from 'dreamland/core'

type Star = {
  x: number
  y: number
  size: number
  speed: number
  phase: number
  shape: 'dot' | 'four-point'
  color: string
}

type StarFieldProps = {
  speedMultiplier: number
  pause?: Delegate<void>
  resume?: Delegate<void>
  setSpeed?: Delegate<number>
  setSpeedEased?: Delegate<number>
}

export const StarField: Component<StarFieldProps, { canvas: HTMLCanvasElement }> = function () {
  let speedMultiplier = this.speedMultiplier
  let targetSpeedMultiplier = speedMultiplier
  let easingStartSpeed = speedMultiplier
  let easingElapsed = 0
  const easingDuration = 1500

  this.setSpeed?.listen((multiplier) => {
    speedMultiplier = Math.max(0, multiplier)
    targetSpeedMultiplier = speedMultiplier
    easingElapsed = easingDuration
  })
  this.setSpeedEased?.listen((multiplier) => {
    easingStartSpeed = speedMultiplier
    targetSpeedMultiplier = Math.max(0, multiplier)
    easingElapsed = 0
  })

  this.cx.mount = (() => {
    const canvas = this.canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('Unable to create a 2D context for the star field')
    }

    const stars: Star[] = []
    let width = 0
    let height = 0
    let paused = false
    let inViewport = false
    let documentVisible = document.visibilityState === 'visible'
    let running = false
    let lastTime = performance.now()
    let resizeTimer: number | undefined

    const resize = () => {
      const bounds = canvas.getBoundingClientRect()
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      const previousWidth = width
      const previousHeight = height
      width = bounds.width
      height = bounds.height

      if (previousWidth > 0 && previousHeight > 0) {
        const widthScale = width / previousWidth
        const heightScale = height / previousHeight
        for (const star of stars) {
          star.x *= widthScale
          star.y *= heightScale
        }
      }

      canvas.width = Math.floor(width * pixelRatio)
      canvas.height = Math.floor(height * pixelRatio)
      ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
    }

    const wrapStar = (star: Star) => {
      if (star.x > width + star.size) star.x = -star.size
      if (star.y < -star.size) star.y = height + star.size
    }

    const refresh = (shouldResize = true) => {
      if (shouldResize) {
        resize()
      }
      if (width === 0 || height === 0) {
        return false
      }

      lastTime = performance.now()
      return true
    }

    const syncRunning = (resizeCanvas = true) => {
      const shouldRun = !paused
        && documentVisible
        && inViewport
        && canvas.isConnected
        && width > 0
        && height > 0

      if (shouldRun && !running) {
        running = refresh(resizeCanvas)
      } else {
        running = shouldRun
      }
    }

    const scheduleResize = () => {
      running = false
      if (resizeTimer !== undefined) {
        window.clearTimeout(resizeTimer)
      }
      resizeTimer = window.setTimeout(() => {
        resizeTimer = undefined
        resize()
        syncRunning(false)
      }, 150)
    }

    const draw = (time: number) => {
      if (!running) {
        requestAnimationFrame(draw)
        return
      }

      const elapsed = Math.min((time - lastTime) / 1000, 0.05)
      lastTime = time
      if (easingElapsed < easingDuration) {
        easingElapsed = Math.min(easingDuration, easingElapsed + elapsed * 1000)
        const progress = easingElapsed / easingDuration
        const easedProgress = 1 - Math.pow(1 - progress, 3)
        speedMultiplier = easingStartSpeed
          + (targetSpeedMultiplier - easingStartSpeed) * easedProgress
      }

      ctx.fillStyle = '#000'
      ctx.fillRect(0, 0, width, height)

      if (!paused) {
        for (const star of stars) {
          star.x += elapsed * star.speed * speedMultiplier
          star.y -= elapsed * star.speed * 0.22 * speedMultiplier
          wrapStar(star)

          const twinkle = 0.72 + Math.sin(time / 900 + star.phase) * 0.28
          ctx.fillStyle = star.color
          ctx.globalAlpha = twinkle
          const x = star.x
          const y = star.y

          if (star.shape === 'four-point') {
            ctx.beginPath()
            ctx.moveTo(x, y - star.size)
            ctx.lineTo(x + star.size * 0.28, y - star.size * 0.28)
            ctx.lineTo(x + star.size, y)
            ctx.lineTo(x + star.size * 0.28, y + star.size * 0.28)
            ctx.lineTo(x, y + star.size)
            ctx.lineTo(x - star.size * 0.28, y + star.size * 0.28)
            ctx.lineTo(x - star.size, y)
            ctx.lineTo(x - star.size * 0.28, y - star.size * 0.28)
            ctx.closePath()
            ctx.fill()
          } else {
            ctx.beginPath()
            ctx.arc(x, y, star.size, 0, Math.PI * 2)
            ctx.fill()
          }

          ctx.globalAlpha = 1
        }
      }

      requestAnimationFrame(draw)
    }

    this.pause?.listen(() => {
      paused = true
      syncRunning()
    })
    this.resume?.listen(() => {
      paused = false
      syncRunning()
    })
    const observer = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting
      syncRunning()
    })
    observer.observe(canvas)

    const resizeObserver = new ResizeObserver(() => {
      scheduleResize()
    })
    resizeObserver.observe(canvas)

    const handleVisibilityChange = () => {
      documentVisible = document.visibilityState === 'visible'
      syncRunning()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    resize()
    for (let index = 0; index < 220; index++) {
      const shape = Math.random() < 0.1 ? 'four-point' : 'dot'
      stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: shape === 'four-point' ? Math.random() * 4 + 2 : Math.random() * 1.8 + 0.4,
        speed: Math.random() * 7 + 4,
        phase: Math.random() * Math.PI * 2,
        shape,
        color: '#ffffff',
      })
    }
    requestAnimationFrame(draw)
  })

  return <canvas this={use(this.canvas)} aria-hidden="true"></canvas>
}

StarField.style = css`
  :scope {
    width: 100%;
    height: calc(100svh - 64px);
    position: fixed;
    top: 64px;
    left: 0;
    z-index: -1;
    pointer-events: none;
  }
`
