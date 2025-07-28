const css = new CSSStyleSheet()
css.replaceSync(`
:host {
  --box-border-color: #aaa;
  --box-title-color: #fff;
  --box-background: #ccc;
  --box-margin: 40px 16px 0px;
  --box-padding: 0;
}

.box {
    position: relative;
    margin: var(--box-margin);
    padding: 0px; /*16px;*/
    border: 5px solid var(--box-border-color);
    background: var(--box-background);
    color: #555;
    border-radius: 12px;
}

.box .box-title {
    position: absolute;
    top: -30px;
    line-height: 30px;
    left: 12px;
    padding: 0 16px;
    background: var(--box-border-color);
    border-radius: 5px 5px 0 0;
    color: var(--box-title-color);
    font-weight: bold;
    font-size: 100%;
    text-shadow: 2px 2px 5px #555;
}

.box div {
    margin: 0px; 
    padding: var(--box-padding);
}
`)


class FieldsetBoxElement extends HTMLElement {
    static get observedAttributes() { return ['title']; }

    _shadowRoot = null;

    constructor() {
        super();
        this._shadowRoot = this.attachShadow({mode: "open"});
        this._shadowRoot.adoptedStyleSheets = [css]
    }

    _render() {
        this._shadowRoot.innerHTML = `
          <div class="box">
            <span class="box-title">${this.getAttribute('title')}</span>
            <div>
              <slot></slot>
            </div>
          </div>`;
    }

    connectedCallback() {
        this._render();
    }

    disconnectedCallback() {
    }

    adoptedCallback() {
    }

    attributeChangedCallback(name, oldVal, newVal) {
        if (name === 'title') {
            this._updateTitle(newVal);
        }
    }

    _updateTitle(text) {
        const spanElement = this._shadowRoot.querySelector(".box-title");
        if (spanElement) {
            spanElement.textContent = text;
        }
    }
}

customElements.define("fieldset-box", FieldsetBoxElement);
