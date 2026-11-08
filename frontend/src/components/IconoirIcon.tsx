import { css, type Component } from 'dreamland/core'

type IconoirIconProps = {
  svg: string
  label?: string
}

export const IconoirIcon: Component<IconoirIconProps, { element: HTMLSpanElement | null }> = function () {
  this.element = null
  this.cx.mount = () => {
    if (!this.element) throw new Error('Iconoir icon element was not mounted')
    this.element.innerHTML = this.svg
  }

  return <span class="iconoir-icon" this={use(this.element)} aria-hidden={this.label ? undefined : 'true'} aria-label={this.label}></span>
}

IconoirIcon.style = css`
  :scope {
    display: inline-flex;
    width: 18px;
    height: 18px;
  }

  :scope :global(svg) {
    width: 100%;
    height: 100%;
  }
`
