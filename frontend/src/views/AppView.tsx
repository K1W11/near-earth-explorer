import { css, type Component } from 'dreamland/core'

export const AppView: Component = function () {
  return (
    <section class="view app-view">
    </section>
  )
}

AppView.style = css`
  :scope {
    padding: 48px 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    color:white;
  }
`
