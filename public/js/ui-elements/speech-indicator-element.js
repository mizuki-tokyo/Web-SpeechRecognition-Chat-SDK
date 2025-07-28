const css = new CSSStyleSheet()
css.replaceSync(`
.animation-container {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 120px;
    margin: 20px 0;
}

.waveform {
    display: flex;
    align-items: center;
    gap: 3px;
}

.waveform-bar {
    width: 4px;
    background: linear-gradient(to top, #4facfe 0%, #00f2fe 100%);
    border-radius: 2px;
    animation: waveform 0.6s ease-in-out infinite;
}

@keyframes waveform {
    0%, 100% { height: 10px; }
    50% { height: 50px; }
}
`)


class SpeechIndicatorElement extends HTMLElement {

    _shadowRoot = null;
    _isRunning = false;

    constructor() {
        super();
        this._shadowRoot = this.attachShadow({mode: "open"});
        this._shadowRoot.adoptedStyleSheets = [css]
    }

    _render() {
        this._shadowRoot.innerHTML = `
          <div class="animation-container">
            <div class="waveform" id="waveform">
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
              <div class="waveform-bar" style="animation-play-state:paused;"></div>
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

    attributeChangedCallback(name, oldValue, newValue) {
    }

    async start() {
        if (this._isRunning == false) {
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

            const bars = this._shadowRoot.querySelectorAll(".waveform-bar");
            const length = bars.length;
            if (length > 0) {
                bars[0].style.animationPlayState = '';
                
                for (let i = 1; i < length; i++) {
                    await sleep(100);
                    bars[i].style.animationPlayState = '';
                    bars[length-i].style.animationPlayState = '';
                    if (i >= length-i) {
                        break;
                    }
                }
            }
            this._isRunning = true;
        }
    }

    stop() {
        if (this._isRunning == true) {
            const bars = this._shadowRoot.querySelectorAll(".waveform-bar");
            const onIteration = (e) => {
                e.srcElement.style.animationPlayState = 'paused';
                e.srcElement.onanimationiteration = null;
            };
            bars.forEach(bar => {
                bar.onanimationiteration = onIteration;
            });
        }
        this._isRunning = false;
    }
}

customElements.define("speech-indicator", SpeechIndicatorElement);
