


class AudioRecorder {
    constructor() {
        this.isRecording = false;
        this.audioContext = null;
        this.source = null;
        this.workletNode = null;
        this.processor = null;
        this.websocket = null;
        
        // DOM要素の取得
        this.recordButton = document.getElementById('recordButton');
        this.statusDiv = document.getElementById('status');
        this.audioInfoDiv = document.getElementById('audioInfo');
        this.logDiv = document.getElementById('log');
        this.errorDiv = document.getElementById('error');
        this.currentRecognitionDiv = document.getElementById('currentRecognition');
        this.recognitionHistoryDiv = document.getElementById('recognitionHistory');
        
        // 音声変換器とバッファ管理器を初期化
        this.audioConverter = new AudioConverter();
        this.bufferManager = new AudioBufferManager(this.audioConverter);
        
        this.initializeWebSocket();
        //this.setupEventListeners();
    }
    
    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/audio`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            this.log('WebSocket接続が確立されました');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'vad_result') {
                this.handleVADResult(data);
            } else if (data.type === 'recognition_result') {
                this.handleRecognitionResult(data);
            }
        };
        
        this.websocket.onclose = () => {
            this.log('WebSocket接続が閉じられました');
            this.showError('サーバーとの接続が切断されました');
        };
        
        this.websocket.onerror = (error) => {
            this.log(`WebSocketエラー: ${error}`);
            this.showError('WebSocket接続エラーが発生しました');
        };
    }
    
    // setupEventListeners() {
    //     this.recordButton.addEventListener('click', () => {
    //         if (!this.isRecording) {
    //             this.startRecording();
    //         }
    //     });
    // }
    
    async startRecording() {

        if (this.isRecording) {
            return;
        }

        try {
            this.hideError();
            this.log('マイクへのアクセスを要求中...');
            
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            const actualSampleRate = this.audioContext.sampleRate;
            this.log(`検出されたサンプリングレート: ${actualSampleRate}Hz`);
            this.log(`目標サンプリングレート: 16000Hz`);
            
            this.updateAudioInfo(actualSampleRate);
            this.bufferManager.setInputSampleRate(actualSampleRate);
            
            // AudioWorkletを使用する場合
            if (this.audioContext.audioWorklet) {
                await this.setupAudioWorklet(stream, actualSampleRate);
            } else {
                // フォールバック: ScriptProcessorNode
                this.log('AudioWorklet未対応 - ScriptProcessorNodeを使用');
                await this.setupScriptProcessor(stream);
            }
            
            this.isRecording = true;
            this.updateUI();
            this.log(`録音開始 (${actualSampleRate}Hz -> 16kHz変換)`);
            
        } catch (error) {
            this.log(`録音開始エラー: ${error.message}`);
            this.showError(`マイクアクセスエラー: ${error.message}`);
        }
    }
    
    async setupAudioWorklet(stream, sampleRate) {
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
            
            await this.audioContext.audioWorklet.addModule(workletUrl);
            
            this.source = this.audioContext.createMediaStreamSource(stream);
            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor-worklet');
            
            this.workletNode.port.onmessage = (event) => {
                if (event.data.type === 'audioData' && this.isRecording) {
                    this.processAudioData(event.data.data);
                }
            };
            
            this.source.connect(this.workletNode);
            
            this.log('AudioWorkletNode設定完了');
            URL.revokeObjectURL(workletUrl);
            
        } catch (error) {
            this.log(`AudioWorklet設定エラー: ${error.message}`);
            await this.setupScriptProcessor(stream);
        }
    }
    
    async setupScriptProcessor(stream) {
        this.source = this.audioContext.createMediaStreamSource(stream);
        this.processor = this.audioContext.createScriptProcessor(1024, 1, 1);
        
        this.processor.onaudioprocess = (event) => {
            if (this.isRecording) {
                const inputBuffer = event.inputBuffer.getChannelData(0);
                this.processAudioData(inputBuffer);
            }
        };
        
        this.source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
        
        this.log('ScriptProcessorNode設定完了（フォールバック）');
    }
    
    processAudioData(audioData) {
        if (this.websocket.readyState === WebSocket.OPEN) {
            const convertedData = this.bufferManager.addChunk(audioData);
            if (convertedData) {
                this.websocket.send(convertedData);
                this.log(`音声データ送信: ${convertedData.byteLength} bytes`);
            }
        }
    }
    
    stopRecording() {
        if (this.isRecording) {
            this.isRecording = false;
            
            if (this.bufferManager) {
                const remaining = this.bufferManager.flush();
                if (remaining && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send(remaining);
                    this.log(`最終音声データ送信: ${remaining.byteLength} bytes`);
                }
                this.bufferManager.clear();
            }
            
            if (this.workletNode) {
                this.workletNode.disconnect();
                this.workletNode = null;
            }
            
            if (this.processor) {
                this.processor.disconnect();
                this.processor = null;
            }
            
            if (this.source) {
                this.source.disconnect();
                this.source = null;
            }
            
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
            
            this.updateUI();
            this.log('録音停止');
        }
    }
    
    handleVADResult(data) {
        if (data.speech_detected) {
            this.log('音声検出', 'speech-detected');
            this.updateStatus('音声を検出中...', 'processing');
            this.updateCurrentRecognition('🎤 音声を検出中...', 'processing');
        }
        
        if (data.speech_ended) {
            this.log('音声終了検出', 'speech-ended');
            this.stopRecording();
            this.updateStatus('音声処理完了 - 再度録音可能', 'idle');
            this.updateCurrentRecognition('🔄 音声認識処理中...', 'processing');
        }
    }
    
    handleRecognitionResult(data) {
        const result = data.result;
        
        if (result.error) {
            this.log(`音声認識エラー: ${result.error}`, 'speech-ended');
            this.updateCurrentRecognition(`❌ 認識エラー: ${result.error}`, '');
            return;
        }
        
        const recognizedText = result.text || '';
        this.log(`音声認識結果: ${recognizedText}`, 'speech-detected');
        
        if (recognizedText) {
            this.updateCurrentRecognition(`✅ "${recognizedText}"`, '');
            this.addToHistory(recognizedText, result.segments, data.timestamp);
        } else {
            this.updateCurrentRecognition('🔇 音声が検出されませんでした', '');
        }
    }
    
    updateCurrentRecognition(text, className) {
        this.currentRecognitionDiv.textContent = text;
        this.currentRecognitionDiv.className = `current-recognition ${className}`;
    }
    
    addToHistory(text, segments, timestamp) {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'timestamp';
        const date = new Date(timestamp * 1000);
        timestampDiv.textContent = date.toLocaleTimeString();
        
        const textDiv = document.createElement('div');
        textDiv.className = 'text';
        textDiv.textContent = text;
        
        historyItem.appendChild(timestampDiv);
        historyItem.appendChild(textDiv);
        
        if (segments && segments.length > 0) {
            const segmentsDiv = document.createElement('div');
            segmentsDiv.className = 'segments';
            const segmentTexts = segments.map(seg => 
                `${seg.start.toFixed(1)}s-${seg.end.toFixed(1)}s: ${seg.text}`
            ).join(' | ');
            segmentsDiv.textContent = `セグメント: ${segmentTexts}`;
            historyItem.appendChild(segmentsDiv);
        }
        
        const historyTitle = this.recognitionHistoryDiv.querySelector('.history-title');
        if (historyTitle.nextSibling) {
            this.recognitionHistoryDiv.insertBefore(historyItem, historyTitle.nextSibling);
        } else {
            this.recognitionHistoryDiv.appendChild(historyItem);
        }
        
        const historyItems = this.recognitionHistoryDiv.querySelectorAll('.history-item');
        if (historyItems.length > 10) {
            historyItems[historyItems.length - 1].remove();
        }
    }
    
    updateUI() {
        //onRecordingStart
        //onRecordingStop
        if (this.isRecording) {
            this.recordButton.textContent = '🔴 録音中...';
            this.recordButton.classList.add('recording');
            this.recordButton.disabled = true;
            this.updateStatus('録音中 - 話してください', 'recording');
        } else {
            this.recordButton.textContent = '📱 録音開始';
            this.recordButton.classList.remove('recording');
            this.recordButton.disabled = false;
            this.updateStatus('待機中 - 録音ボタンを押して開始', 'idle');
        }
    }
    
    updateStatus(message, className) {
        //onUpdateStatus
        this.statusDiv.textContent = message;
        this.statusDiv.className = `status ${className}`;
    }
    
    updateAudioInfo(sampleRate) {
        //onUpdateAudioInfo
        const conversionNeeded = sampleRate !== 16000;
        const message = `入力: ${sampleRate}Hz/Float32 → 出力: 16000Hz/16bit ${conversionNeeded ? '(変換中)' : '(変換不要)'}`;
        this.audioInfoDiv.textContent = message;
        this.audioInfoDiv.className = `status ${conversionNeeded ? 'processing' : 'idle'}`;
    }
    
    log(message, className = '') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${className}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        this.logDiv.appendChild(logEntry);
        this.logDiv.scrollTop = this.logDiv.scrollHeight;
    }
    
    showError(message) {
        this.errorDiv.textContent = message;
        this.errorDiv.style.display = 'block';
    }
    
    hideError() {
        this.errorDiv.style.display = 'none';
    }
}

//#################################
// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    const recorder = new AudioRecorder();
    window.currentRecorder = recorder; // デバッグ用


    // DOM要素の取得
    recordButton = document.getElementById('recordButton');
    statusDiv = document.getElementById('status');
    audioInfoDiv = document.getElementById('audioInfo');
    logDiv = document.getElementById('log');
    errorDiv = document.getElementById('error');
    currentRecognitionDiv = document.getElementById('currentRecognition');
    recognitionHistoryDiv = document.getElementById('recognitionHistory');

    recordButton.addEventListener('click', () => {
        recorder.startRecording();
    });
});
