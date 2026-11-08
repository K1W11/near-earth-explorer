import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { css, type Component } from 'dreamland/core'

type MarkdownContentProps = {
  content: string
}

const renderMarkdown = (content: string) => {
  const html = marked.parse(content, { async: false })
  if (typeof html !== 'string' || typeof window === 'undefined') return ''
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  })
}

export const MarkdownContent: Component<MarkdownContentProps, { element: HTMLElement | null }> = function () {
  this.element = null
  const update = () => {
    if (this.element) this.element.innerHTML = renderMarkdown(this.content)
  }
  use(this.content).listen(update)
  this.cx.mount = () => {
    update()
  }

  return <div class="markdown-content" this={use(this.element)}></div>
}

MarkdownContent.style = css`
  :scope {
    font-size: 11px;
    line-height: 1.45;
  }

  :scope :first-child {
    margin-top: 0;
  }

  :scope :last-child {
    margin-bottom: 0;
  }

  :scope p,
  :scope ul,
  :scope ol,
  :scope pre,
  :scope blockquote {
    margin: 0 0 8px;
  }

  :scope ul,
  :scope ol {
    padding-left: 18px;
  }

  :scope code {
    padding: 1px 3px;
    border-radius: 3px;
    background: rgb(255 255 255 / 10%);
    font: inherit;
  }

  :scope pre {
    overflow-x: auto;
    padding: 8px;
    border-radius: 4px;
    background: rgb(0 0 0 / 35%);
  }

  :scope pre code {
    padding: 0;
    background: transparent;
  }

  :scope a {
    color: #62d9ff;
  }
`
