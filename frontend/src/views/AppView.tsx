import { css, type Component } from 'dreamland/core'
import earthDark from "../assets/pixelearth.png";


export const AppView: Component<{}, { earth: HTMLImageElement }> = function () {
  this.cx.mount = () => {
    let rotation = 0
    let previousTime = performance.now()

    const rotate = (time: number) => {
      const elapsed = Math.min((time - previousTime) / 1000, 0.05)
      previousTime = time
      rotation = (rotation + elapsed * 8) % 360
      this.earth.style.transform = `translateY(50%) rotate(${rotation}deg)`
      requestAnimationFrame(rotate)
    }

    requestAnimationFrame(rotate)
  }

  return (
    <section class="view app-view">
      <img this={use(this.earth)} src={earthDark}></img>
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
    color:white;
  }

  :scope img {
    position: absolute;
    bottom: 0;
    width: min(650px, 90vw);
    image-rendering: pixelated;
    height: auto;
    transform: translateY(50%);
    transform-origin: center;
  }
`
