import { css, type Delegate } from 'dreamland/core'
import { Link, type LayoutComponent } from 'dreamland/router'
import { StarField } from './StarField'

export const createLayout = (setStarSpeedEased: Delegate<number>): LayoutComponent => {
  const Layout: LayoutComponent = function () {
    const setSpeedForRoute = (path: string) => {
      if (path === '/app') {
        setStarSpeedEased(0.55)
      } else if (path === '/') {
        setStarSpeedEased(2.4)
      } else {
        setStarSpeedEased(10)
      }
    }

    use(this.routerState.path).listen(setSpeedForRoute)
    queueMicrotask(() => setSpeedForRoute(this.routerState.path))

    return (
      <div class="site-shell">
        <header class="site-header">
          <Link href="/" class="site-brand">Near Earth Explorer</Link>
          <nav class="site-nav" aria-label="Primary navigation">
            <Link href="/">Home</Link>
            <Link href="/app">App</Link>
          </nav>
        </header>
        <main class="site-content">
          <StarField speedMultiplier={1} setSpeedEased={setStarSpeedEased} />
          {use(this.routerState.outlet)}
        </main>
      </div>
    )
  }

  Layout.style = css`
  :scope {
    height: 100svh;
    display: flex;
    flex-direction: column;
  }

  :scope .site-header {
    flex: 0 0 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    color: white;
    border-bottom: 1px solid white;
  }

  :scope .site-brand {
    font-weight: 700;
  }

  :scope .site-nav {
    display: flex;
    gap: 20px;
    font-size: 14px;
  }

  :scope .site-nav a:hover,
  :scope .site-nav a:focus-visible {
    color: #242424;
  }

  :scope .site-content {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
  }

  :scope .site-content > * {
    min-height: 0;
  }

  :scope .site-content > :not(canvas) {
    min-height: 100%;
  }

  :scope fieldset {
    all: unset;
  }
  `

  return Layout
}
