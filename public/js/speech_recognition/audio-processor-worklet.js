// audio-processor-worklet.js
// AudioWorkletProcessorの実装

class AudioProcessorWorklet extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 1024;
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
        
        // メインスレッドからのメッセージを受信
        this.port.onmessage = (event) => {
            if (event.data.command === 'updateBufferSize') {
                this.bufferSize = event.data.size;
                this.buffer = new Float32Array(this.bufferSize);
                this.bufferIndex = 0;
            }
        };
    }
    
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        
        // 入力がない場合は処理を続行
        if (!input || input.length === 0) {
            return true;
        }
        
        const inputChannel = input[0]; // モノラル入力を想定
        
        if (!inputChannel) {
            return true;
        }
        
        // 入力データをバッファに蓄積
        for (let i = 0; i < inputChannel.length; i++) {
            this.buffer[this.bufferIndex] = inputChannel[i];
            this.bufferIndex++;
            
            // バッファが満杯になったらメインスレッドに送信
            if (this.bufferIndex >= this.bufferSize) {
                // データをコピーして送信
                const audioData = new Float32Array(this.buffer);
                
                this.port.postMessage({
                    type: 'audioData',
                    data: audioData,
                    timestamp: currentTime
                });
                
                // バッファをリセット
                this.bufferIndex = 0;
            }
        }
        
        // プロセッサを継続
        return true;
    }
}

// AudioWorkletProcessorとして登録
registerProcessor('audio-processor-worklet', AudioProcessorWorklet);
