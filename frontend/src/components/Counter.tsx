import { css, type Component } from 'dreamland/core'

export const Counter: Component<{}, { count: number }> = function () {
  this.count = 0

  return (
    <section class="counter-card">
      <p class="eyebrow">Demo app</p>
      <h1>Counter</h1>
      <p class="count">{use(this.count)}</p>
      <button type="button" on:click={() => this.count++}>
        Increment
      </button>
    </section>
  )
}

Counter.style = css`
  :scope {
    width: min(100%, 360px);
    padding: 40px;
    text-align: center;
    color:white;
    border: 4px solid white;
    border-radius: 12px;
    box-shadow: 0 12px 30px rgb(0 0 0 / 6%);
  }

  :scope .eyebrow {
    margin: 0 0 12px;
    font-size: 12px;
    letter-spacing: .08em;
    text-transform: uppercase;
  }

  :scope h1 {
    margin: 0;
    font-size: 32px;
  }

  :scope .count {
    margin: 24px 0;
    font-size: 56px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  :scope button {
    display: inline-block;
    padding: 10px 18px;
    color: white;
    background: #242424;
    border: 0;
    border-radius: 6px;
    cursor: pointer;
  }

  :scope button:hover {
    background: #444;
  }

  :scope button:focus-visible {
    outline: 3px solid #9db8ff;
    outline-offset: 3px;
  }
`
