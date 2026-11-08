export abstract class CanvasController {
  protected readonly canvas: HTMLCanvasElement
  protected readonly context: CanvasRenderingContext2D
  protected width = 0
  protected height = 0
  get size() {
    return { width: this.width, height: this.height }
  }
  private frame = 0
  private resizeTimer: number | undefined
  private resizeObserver: ResizeObserver
  private running = true
  private previousTime = performance.now()

  constructor(canvas: HTMLCanvasElement, contextError: string) {
    this.canvas = canvas
    const context = canvas.getContext('2d')
    if (!context) throw new Error(contextError)
    this.context = context
    this.resizeObserver = new ResizeObserver(() => this.scheduleResize())
  }

  start() {
    this.resizeObserver.observe(this.canvas)
    this.resize()
    this.frame = requestAnimationFrame((time) => this.loop(time))
  }

  setRunning(running: boolean) {
    this.running = running
    if (running) this.previousTime = performance.now()
  }

  stop() {
    cancelAnimationFrame(this.frame)
    this.resizeObserver.disconnect()
    if (this.resizeTimer !== undefined) window.clearTimeout(this.resizeTimer)
    this.context.clearRect(0, 0, this.width, this.height)
  }

  protected abstract render(time: number, elapsed: number): void

  private loop(time: number) {
    if (!this.canvas.isConnected) {
      this.stop()
      return
    }
    const elapsed = Math.min((time - this.previousTime) / 1000, 0.05)
    this.previousTime = time
    if (this.running) this.render(time, elapsed)
    this.frame = requestAnimationFrame((nextTime) => this.loop(nextTime))
  }

  private resize() {
    const bounds = this.canvas.getBoundingClientRect()
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
    const previousWidth = this.width
    const previousHeight = this.height
    this.width = bounds.width
    this.height = bounds.height
    this.canvas.width = Math.floor(this.width * pixelRatio)
    this.canvas.height = Math.floor(this.height * pixelRatio)
    this.context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
    this.onResize(previousWidth, previousHeight)
  }

  protected onResize(_previousWidth: number, _previousHeight: number) {}

  private scheduleResize() {
    if (this.resizeTimer !== undefined) window.clearTimeout(this.resizeTimer)
    this.resizeTimer = window.setTimeout(() => {
      this.resizeTimer = undefined
      this.resize()
    }, 150)
  }
}
