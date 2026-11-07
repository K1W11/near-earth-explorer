import type { Component, ComponentChild } from "dreamland/core"

export function setupCounter(element: HTMLButtonElement) {
  let counter = 0
  const setCounter = (count: number) => {
    counter = count
    element.innerHTML = `Count is ${counter}`
  }
  element.addEventListener('click', () => setCounter(counter + 1))
  setCounter(0)
}

export const Counter: Component<{}, { count: number }> = function () {
    // Initialize the internal state
    this.count = 0;

    return (
        <div>
            <h2>Counter Example</h2>
            {/* Bind the click listener and track state reactively with use() */}
            <button on:click={() => this.count++}>
                Clicks: {use(this.count)}
            </button>
        </div>
    );
};