import { css, type Component } from 'dreamland/core'
import { Link } from 'dreamland/router'

export const MainView: Component = function () {
  return (
    <section class="view main-view">
      <p class="eyebrow">Welcome</p>
      <h1>Near Earth Explorer</h1>
      <p class="intro">A blank starting point for the main page.</p>
      <Link href="/app" class="button-link">Open the app</Link>

      {new Array(20).fill(0).map((_, i) => (
        <p key={i}>This is some filler content to make the page scrollable.</p>
      ))}
    </section>
  )
}

MainView.style = css`
  :scope {
    width: 100%;
    padding: 48px 24px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    max-width: 768px;
    margin: 0 auto;
  }

  :scope .eyebrow {
    margin: 0 0 12px;
    font-size: 12px;
    letter-spacing: .08em;
    text-transform: uppercase;
  }

  :scope h1 {
    margin: 0;
    font-size: clamp(32px, 7vw, 56px);
  }

  :scope .intro {
    margin: 16px 0 28px;
  }
 
  :scope .button-link {
    display: inline-block;
    padding: 10px 18px;
    background: #242424;
    border-radius: 6px;
  }

  :scope .button-link:focus-visible {
    outline: 3px solid #9db8ff;
    outline-offset: 3px;
  }
`
