

const css = new CSSStyleSheet()
css.replaceSync(`
:host {
  --background-color: #ccc;
  --checked-background-color: #2196F3;
  --disabled-background-color: dimgray;
  --knob-color: white;
  --disabled-knob-color: lightgray;
}

.toggle-switch {
    display: flex;
    align-items: center;
    gap: 10px;
}

.switch {
    position: relative;
    width: 50px;
    height: 24px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--background-color);
    transition: .4s;
    border-radius: 24px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: var(--knob-color);
    transition: .4s;
    border-radius: 50%;
}

input:checked + .slider {
    background-color: var(--checked-background-color); /*#2196F3;*/
}

input:checked + .slider:before {
    transform: translateX(26px);
}

/* === "input:disabled + ..." must be defined after "input:checked + ..." === */
input:disabled + .slider {
    background-color: var(--disabled-background-color);
}

input:disabled + .slider:before {
    background-color: var(--disabled-knob-color);
}
`)


class ToggleSwitchElement extends HTMLElement {
    static get observedAttributes() { return ['checked']; }

    _shadowRoot = null;

    constructor() {
        super();
        this._shadowRoot = this.attachShadow({mode: "open"});
        this._shadowRoot.adoptedStyleSheets = [css]
    }

    _render() {
        const checked = (this.getAttribute('checked') === null)? "" : "checked";
        this._shadowRoot.innerHTML = `
          <span class="toggle-switch">
            <label class="switch">
              <input type="checkbox" id="isEnabled" ${checked}>
              <span class="slider"></span>
            </label>
            <span id="statusText">Disabled</span>
          </span>`;
    }

    connectedCallback() {
        this._render();

        const statusText = this._shadowRoot.querySelector("#statusText");
        this._shadowRoot.querySelector("#isEnabled").addEventListener("change", (e) => {
            statusText.textContent = e.target.checked? "Enabled" : "Disabled";
        });
    }

    disconnectedCallback() {
    }

    adoptedCallback() {
    }

    get value() {
        return this._shadowRoot.querySelector("#isEnabled").checked;
    }

    set value(enabled) {
        this._shadowRoot.querySelector("#isEnabled").checked = enabled;
    }

    get checked() {
        return this._shadowRoot.querySelector("#isEnabled").checked;
    }

    set checked(enabled) {
        this._shadowRoot.querySelector("#isEnabled").checked = enabled;
    }

    get disabled() {
        return this._shadowRoot.querySelector("#isEnabled").disabled;
    }

    set disabled(value) {
        this._shadowRoot.querySelector("#isEnabled").disabled = value;
    }

    addEventListener(type, listener) {
        this._shadowRoot.querySelector("#isEnabled").addEventListener(type, listener);
    }

    removeEventListener(type, listener) {
        this._shadowRoot.querySelector("#isEnabled").removeEventListener(type, listener);
    }

    get onchange() {
        return this._shadowRoot.querySelector("#isEnabled").onchange;
    }

    set onchange(listener) {
        this._shadowRoot.querySelector("#isEnabled").onchange = listener;
    }

    attributeChangedCallback(name, oldVal, newVal) {
        if (name === 'checked') {
            if (this.getAttribute('checked') === null) {
                this._shadowRoot.querySelector("#isEnabled").removeAttribute('checked');
            } else {
                this._shadowRoot.querySelector("#isEnabled").setAttribute('checked', "");
            }
        }
    }
}

customElements.define("toggle-switch", ToggleSwitchElement);
