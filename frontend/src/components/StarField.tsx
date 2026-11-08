import { css, type Component, type Delegate } from 'dreamland/core'
import { CanvasController } from './CanvasController'

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
    const stars: Star[] = []
    let paused = false
    let inViewport = false
    let documentVisible = document.visibilityState === 'visible'
    const controller = new class extends CanvasController {
      protected onResize(previousWidth: number, previousHeight: number) {
        if (previousWidth > 0 && previousHeight > 0) {
          for (const star of stars) {
            star.x *= this.width / previousWidth
            star.y *= this.height / previousHeight
          }
        }
      }

      protected render(_time: number, elapsed: number) {
        const { context: ctx, width, height } = this
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
          if (star.x > width + star.size) star.x = -star.size
          if (star.y < -star.size) star.y = height + star.size

          const twinkle = 0.72 + Math.sin(_time / 900 + star.phase) * 0.28
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

      }
    }(canvas, 'Unable to create a 2D context for the star field')

    this.pause?.listen(() => {
      paused = true
      controller.setRunning(false)
    })
    this.resume?.listen(() => {
      paused = false
      controller.setRunning(!paused && documentVisible && inViewport)
    })
    const observer = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting
      controller.setRunning(!paused && documentVisible && inViewport)
    })
    observer.observe(canvas)


    const handleVisibilityChange = () => {
      documentVisible = document.visibilityState === 'visible'
      controller.setRunning(!paused && documentVisible && inViewport)
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    controller.start()
    inViewport = true
    controller.setRunning(!paused && documentVisible)
    for (let index = 0; index < 220; index++) {
      const shape = Math.random() < 0.1 ? 'four-point' : 'dot'
      stars.push({
        x: Math.random() * controller.size.width,
        y: Math.random() * controller.size.height,
        size: shape === 'four-point' ? Math.random() * 4 + 2 : Math.random() * 1.8 + 0.4,
        speed: Math.random() * 7 + 4,
        phase: Math.random() * Math.PI * 2,
        shape,
        color: '#ffffff',
      })
    }
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
