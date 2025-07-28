import { AudioConverter, AudioBufferManager } from "./audio-converter.js";

export default class SpeechRecognizer {

    logger = console;
    lang = "en";
    continuous = false;
    prompt = ""

    #eventListenerMap = new Map();
    #eventList = Object.freeze(["start", "end", "speechstart", "speechend", "result", "nomatch", "error"])
    
    #isRecording = false;
    #isStarted = false;

    #audioContext = null;
    #source = null;
    #workletNode = null;
    #processor = null;
    #websocket = null;

    #audioConverter = null;
    #bufferManager = null;

    constructor() {
        // 音声変換器とバッファ管理器を初期化
        this.#audioConverter = new AudioConverter();
        this.#bufferManager = new AudioBufferManager(this.#audioConverter);

        this.#initializeEventListeners();
    }

    #initializeEventListeners() {
        this.#eventList.forEach((type) => {
            this["on" +  type] = null;
            this.#eventListenerMap.set(type, [])
        });
    }

    async #openSocket() {
        return new Promise((resolve, reject) => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/audio`;
            const websocket = new WebSocket(wsUrl);

            websocket.onopen = () => {
                resolve(websocket);
            };

            websocket.onerror = (error) => {
                if (! error.message) {
                    error.message = "Failed to open WebSocket";
                }
                reject(error);
            }
        });
    }


    async #connect() {
        if (this.#websocket != null &&
            this.#websocket.readyState != WebSocket.CLOSING && this.#websocket.readyState == WebSocket.CLOSED) {

            if (this.#websocket.readyState == WebSocket.CONNECTING) {
                // If it is connecting, wait a moment.
                const sleep = (msec) => new Promise(resolve => setTimeout(resolve, msec));
                let count = 0;
                while ((this.#websocket.readyState == WebSocket.CONNECTING) && (++count < 100)) {
                    await sleep(50);
                }
            }
            if (this.#websocket.readyState == WebSocket.OPEN) {
                return true;
            }
            // Give up connecting.
            this.#websocket.close(1000);
        }

        try {
            // Try connecting to server with websocket.
            this.#websocket = await this.#openSocket();

            // Connection succeeded.
            this.logger.info("WebSocket connection established");
            this.#websocket.send(JSON.stringify({lang:this.lang, prompt:this.prompt}));
            this.#resourceStateChanged();

        } catch (error) {
            // Connection failed.
            this.#dispatchEvent("error", error);
            return false;
        }

        // Set up websocket handlers.
        const websocket = this.#websocket;
        websocket._sessionId = "";
        websocket._stopRequested = false;
        websocket._recognizing = false;
        websocket._endmark = false;

        this.#websocket.onerror = (error) => {
            this.logger.error(`WebSocket error: ${error}`);

            if (typeof error === "string") {
                error = {message: error};
            } else if (! ("message" in error)) {
                error.message = "WebSocket connection error occurred";
            }
            this.#dispatchEvent("error", error);
        };

        this.#websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'vad_result') {
                if (data.speech_detected) {
                    websocket._recognizing = true;
                }
                this.#handleVADResult(data);

            } else if (data.type === 'recognition_result') {
                websocket._recognizing = false;
                try {
                    this.#handleRecognitionResult(data);
                } finally {
                    if (this.continuous == false || websocket._stopRequested == true) {
                        this.#disconnect(websocket);
                    }
                }
            }
        };

        this.#websocket.onclose = () => {
            this.logger.info("WebSocket connection closed");
            if (this.#isRecording) {
                this.#stopRecording();
                const error = {message: "Connection to server was lost"};
                this.#dispatchEvent("error", error);
            }
            this.#resourceStateChanged();
        };

        return true;
    }

    #disconnect(websocket = null) {
        if (websocket == null) {
            websocket = this.#websocket;
        }

        if (websocket == null ||
            websocket.readyState == WebSocket.CLOSING || websocket.readyState == WebSocket.CLOSED) {
            return;
        }
        websocket.close(1000);
    }


    #dispatchEvent(type, param)
    {
        if (this.#eventList.includes(type)) {
            const handler = this["on" +  type];
            if (typeof handler === "function") {
                try {
                    handler(param);
                } catch (error) {
                    this.logger.error(error);
                }
            }
            const listeners = this.#eventListenerMap.get(type);
            if (Array.isArray(listeners)) {
                listeners.forEach((listener) => {
                    if (typeof listener === "function") {
                        try {
                            listener(param);
                        } catch (error) {
                            this.logger.error(error);
                        }
                    }
                });
            }
        }
    }

    
    async #setupAudioWorklet(stream, sampleRate) {
        try {
            const workletCode = `
                        class AudioProcessorWorklet extends AudioWorkletProcessor {
                            constructor() {
                                super();
                                this.bufferSize = 1024;
                                this.buffer = new Float32Array(this.bufferSize);
                                this.bufferIndex = 0;
                            }
                            
                            process(inputs, outputs, parameters) {
                                const input = inputs[0];
                                if (!input || input.length === 0) return true;
                                
                                const inputChannel = input[0];
                                if (!inputChannel) return true;
                                
                                for (let i = 0; i < inputChannel.length; i++) {
                                    this.buffer[this.bufferIndex] = inputChannel[i];
                                    this.bufferIndex++;
                                    
                                    if (this.bufferIndex >= this.bufferSize) {
                                        const audioData = new Float32Array(this.buffer);
                                        this.port.postMessage({
                                            type: 'audioData',
                                            data: audioData,
                                            timestamp: currentTime
                                        });
                                        this.bufferIndex = 0;
                                    }
                                }
                                return true;
                            }
                        }
                        registerProcessor('audio-processor-worklet', AudioProcessorWorklet);
                    `;
            
            const workletBlob = new Blob([workletCode], { type: 'application/javascript' });
            const workletUrl = URL.createObjectURL(workletBlob);
            
            await this.#audioContext.audioWorklet.addModule(workletUrl);
            
            this.#source = this.#audioContext.createMediaStreamSource(stream);
            this.#workletNode = new AudioWorkletNode(this.#audioContext, 'audio-processor-worklet');
            
            this.#workletNode.port.onmessage = (event) => {
                if (event.data.type === 'audioData' && this.#isRecording) {
                    this.#processAudioData(event.data.data);
                }
            };
            
            this.#source.connect(this.#workletNode);
            
            this.logger.info('AudioWorkletNode setup complete');
            URL.revokeObjectURL(workletUrl);
            
        } catch (error) {
            this.logger.info(`AudioWorklet setup error: ${error.message}`);
            await this.#setupScriptProcessor(stream);
        }
    }
    
    async #setupScriptProcessor(stream) {
        this.#source = this.#audioContext.createMediaStreamSource(stream);
        this.#processor = this.#audioContext.createScriptProcessor(1024, 1, 1);
        
        this.#processor.onaudioprocess = (event) => {
            if (this.#isRecording) {
                const inputBuffer = event.inputBuffer.getChannelData(0);
                this.#processAudioData(inputBuffer);
            }
        };
        
        this.#source.connect(this.#processor);
        this.#processor.connect(this.#audioContext.destination);
        
        this.logger.info('ScriptProcessorNode setup complete (fallback)');
    }
    
    #processAudioData(audioData) {
        if (this.#websocket != null && this.#websocket.readyState === WebSocket.OPEN) {
            const convertedData = this.#bufferManager.addChunk(audioData);
            if (convertedData) {
                this.#websocket.send(convertedData); // convertedData: ArrayBuffer
                this.logger.info(`Sending audio data: ${convertedData.byteLength} bytes`);                
            }
        }
    }

    #resourceStateChanged() {
        let isConnected = this.#websocket != null && this.#websocket.readyState === WebSocket.OPEN;

        if (this.#isRecording && isConnected) { // [recording] and [connected]
            if (this.#isStarted == false) {
                this.#dispatchEvent("start");
                this.#isStarted = true;
            }
        } else if (! isConnected) { // [not connected]
            if (this.#isStarted == true) {
                this.#dispatchEvent("end");
                this.#isStarted = false;
            }
        }
        // else {
        //     if (this.#isStarted) {
        //         this.#dispatchEvent("end");
        //         this.#isStarted = false;
        //     }
        // }
    }

    #handleVADResult(data) {
        if (data.speech_detected) {
            this.#dispatchEvent("speechstart", data);
        }
        
        if (data.speech_ended) {
            // If continuous speech recognition is enabled at the server side,
            // it is possible that continuous speech recognition will be performed.
            // If you want to stop recording when the speech segment ends, 
            // you should call stopRecording() in the speechend event handler.

            if (this.continuous == false) {
                this.#stopRecording();
            } else {
                this.#bufferManager.clear();
            }
            this.#dispatchEvent("speechend", data);
        }
    }

    #handleRecognitionResult(data) {
        const result = data.result;
        
        if (result.error) {
            const error = result.error;
            if (! ("message" in error)) {
                error.message = "Speech recognition error";
            }
            this.#dispatchEvent("error", error);
            return;
        }
        
        const recognizedText = result.text || '';        
        if (recognizedText) {
            this.#dispatchEvent("result", data);
        } else {
            this.#dispatchEvent("nomatch", data);
        }
    }

    addEventListener(type, listener) {
        if (this.#eventList.includes(type) && typeof listener === "function") {
            const listeners = this.#eventListenerMap.get(type);
            if (! Array.isArray(listeners)) {
                this.#eventListenerMap.set(listeners = []);
            }
            if (! listeners.includes(listener)) {
                listeners.push(listener);
            }
        }
    }

    isRecording() {
        return this.#isRecording;
    }

    async start() {
        const promise = this.#connect();
        let isConnected = false;

        if (await this.#startRecording()) {
            isConnected = await promise;
            if (isConnected == false) {
                this.#stopRecording();
            }
        }

        return isConnected;
    }

    stop() {
        this.#stopRecording();

        const websocket = this.#websocket;
        if (websocket._recognizing == false) {
            // 認識中でなければソケットを切断
            this.#disconnect(websocket);
        } else {
            // 認識中の場合
            websocket._stopRequested = true;
            if (websocket != null) {
                setTimeout(10000, () => {
                    if (websocket._recognizing) {
                        //////// TODO
                        ///this.#dispatchEvent("error", error);
                    }
                    this.#disconnect(websocket);
                });
            }
        }
    }

    async #startRecording() {
        if (this.#isRecording == true) {
            return true;
        }

        //this.#connect();

        try {
            this.logger.info("Requesting microphone access...");

            // まずデバイスの制約なしでストリームを取得
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // AudioContext を作成（ブラウザのデフォルトサンプリングレートを使用）
            this.#audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // 実際のサンプリングレートをログに記録
            const actualSampleRate = this.#audioContext.sampleRate;
            this.logger.info(`Detected sample rate: ${actualSampleRate}Hz`);
            this.logger.info(`Target sample rate: 16000Hz`);
            
            this.#bufferManager.setInputSampleRate(actualSampleRate);
            
            // AudioWorklet を使用する場合
            if (this.#audioContext.audioWorklet) {
                await this.#setupAudioWorklet(stream, actualSampleRate);
            } else {
                // フォールバック: ScriptProcessorNode
                this.logger.info("AudioWorklet not supported – using ScriptProcessorNode");
                await this.#setupScriptProcessor(stream);
            }

            this.#isRecording = true;
            this.logger.info(`Recording started (converting from ${actualSampleRate}Hz to 16kHz)`)

            this.#resourceStateChanged();
            return true;
            
        } catch (error) {
            this.#dispatchEvent("error", error);
            this.logger.error(`Recording start error: ${error.message}`)
            return false;
        }
    }


    #stopRecording() {
        if (this.#isRecording) {
            this.#isRecording = false;

            if (this.#bufferManager) {
                if (this.#websocket != null && this.#websocket.readyState === WebSocket.OPEN) {
                    const remaining = this.#bufferManager.flush();
                    if (remaining) {
                        this.#websocket.send(remaining);
                        this.logger.info(`Final audio data sent: ${remaining.byteLength} bytes`);
                    }

                    if (this.#websocket._recognizing) {
                        let length = 16000 * 3/*sec*/;
                        this.#websocket.send((new Int16Array(length)).buffer); // Send silent data
                        this.#websocket._endmark = true;
                        this.logger.info(`Silent data sent`);
                    }
                }
                this.#bufferManager.clear();
            }
            
            if (this.#workletNode) {
                this.#workletNode.disconnect();
                this.#workletNode = null;
            }
            
            if (this.#processor) {
                this.#processor.disconnect();
                this.#processor = null;
            }
            
            if (this.#source) {
                this.#source.disconnect();
                this.#source = null;
            }
            
            if (this.#audioContext) {
                this.#audioContext.close();
                this.#audioContext = null;
            }

            this.#resourceStateChanged();
            this.logger.info('Recording stopped');
        }
    }
}
