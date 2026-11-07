import './style.css'
import type { Component } from 'dreamland/core'

const Counter: Component<{}, { count: number }> = function () {
  this.count = 0

  return (
    <main class="counter-demo">
      <section class="counter-card">
        <p class="eyebrow">abc abc abc abc</p>
        <h1>Counter</h1>
        <p class="count">{use(this.count)}</p>
        <button type="button" on:click={() => this.count++}>
          Increment
        </button>
      </section>
    </main>
  )
}

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('App mount point #app was not found')
}

app.append(<Counter />)
