import { css, type Component } from 'dreamland/core'
import { Link } from 'dreamland/router'

export const NotFoundView: Component = function () {
  return (
    <section class="not-found-view">
    
      <p class="eyebrow">404</p>
      <h1>Lost in space</h1>
      <p class="message">The page you're looking for has drifted out of orbit.</p>
      <Link href="/" class="button-link">Return home</Link>
    </section>
  )
}

NotFoundView.style = css`
  :scope {
    padding: 48px 24px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    min-height: 100%;
    max-width: 720px;
    margin: auto;
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

  :scope .message {
    margin: 16px 0 28px;
  }

  :scope .button-link {
    display: inline-block;
    padding: 10px 18px;
    color: white;
    background: #242424;
    border-radius: 6px;
  }

  :scope .button-link:hover,
  :scope .button-link:focus-visible {
    background: #444;
  }

  :scope .button-link:focus-visible {
    outline: 3px solid #9db8ff;
    outline-offset: 3px;
  }
`
