/**
 * 音声リサンプリングとフォーマット変換ユーティリティ
 */
class AudioConverter {
    constructor() {
        this.targetSampleRate = 16000; // Whisper用の目標サンプリングレート
        this.targetBitDepth = 16;      // 目標ビット深度
    }

    /**
     * Float32配列を16bit PCMに変換
     * @param {Float32Array} float32Array - 入力音声データ (-1.0 to 1.0)
     * @returns {Int16Array} - 16bit PCM音声データ
     */
    float32To16BitPCM(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            // -1.0 から 1.0 の範囲を -32768 から 32767 にマップ
            const sample = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        }
        return int16Array;
    }

    /**
     * 16bit PCMをFloat32配列に変換
     * @param {Int16Array} int16Array - 16bit PCM音声データ
     * @returns {Float32Array} - Float32音声データ (-1.0 to 1.0)
     */
    int16ToFloat32(int16Array) {
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7FFF);
        }
        return float32Array;
    }

    /**
     * 線形補間によるリサンプリング
     * @param {Float32Array} inputBuffer - 入力音声データ
     * @param {number} inputSampleRate - 入力サンプリングレート
     * @param {number} outputSampleRate - 出力サンプリングレート
     * @returns {Float32Array} - リサンプリング後の音声データ
     */
    linearResample(inputBuffer, inputSampleRate, outputSampleRate) {
        if (inputSampleRate === outputSampleRate) {
            return new Float32Array(inputBuffer);
        }

        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.round(inputBuffer.length / ratio);
        const outputBuffer = new Float32Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
            const position = i * ratio;
            const index = Math.floor(position);
            const fraction = position - index;

            if (index + 1 < inputBuffer.length) {
                // 線形補間
                outputBuffer[i] = inputBuffer[index] * (1 - fraction) + 
                                 inputBuffer[index + 1] * fraction;
            } else {
                outputBuffer[i] = inputBuffer[index] || 0;
            }
        }

        return outputBuffer;
    }

    /**
     * 高品質なリサンプリング（ランチョス補間）
     * @param {Float32Array} inputBuffer - 入力音声データ
     * @param {number} inputSampleRate - 入力サンプリングレート
     * @param {number} outputSampleRate - 出力サンプリングレート
     * @param {number} a - ランチョスカーネルのサイズ（デフォルト: 3）
     * @returns {Float32Array} - リサンプリング後の音声データ
     */
    lanczoResample(inputBuffer, inputSampleRate, outputSampleRate, a = 3) {
        if (inputSampleRate === outputSampleRate) {
            return new Float32Array(inputBuffer);
        }

        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.round(inputBuffer.length / ratio);
        const outputBuffer = new Float32Array(outputLength);

        // ランチョス関数
        const lanczos = (x) => {
            if (x === 0) return 1;
            if (Math.abs(x) >= a) return 0;
            return (a * Math.sin(Math.PI * x) * Math.sin(Math.PI * x / a)) / 
                   (Math.PI * Math.PI * x * x);
        };

        for (let i = 0; i < outputLength; i++) {
            const center = i * ratio;
            let sum = 0;
            let weightSum = 0;

            const start = Math.floor(center - a + 1);
            const end = Math.floor(center + a);

            for (let j = start; j <= end; j++) {
                if (j >= 0 && j < inputBuffer.length) {
                    const weight = lanczos(center - j);
                    sum += inputBuffer[j] * weight;
                    weightSum += weight;
                }
            }

            outputBuffer[i] = weightSum > 0 ? sum / weightSum : 0;
        }

        return outputBuffer;
    }

    /**
     * 最適なリサンプリング方法を選択
     * @param {Float32Array} inputBuffer - 入力音声データ
     * @param {number} inputSampleRate - 入力サンプリングレート
     * @param {number} outputSampleRate - 出力サンプリングレート
     * @param {string} quality - 品質設定 ('fast' | 'good' | 'high')
     * @returns {Float32Array} - リサンプリング後の音声データ
     */
    resample(inputBuffer, inputSampleRate, outputSampleRate = this.targetSampleRate, quality = 'good') {
        console.log(`Resampling: ${inputSampleRate}Hz -> ${outputSampleRate}Hz (${quality} quality)`);
        
        switch (quality) {
            case 'fast':
                return this.linearResample(inputBuffer, inputSampleRate, outputSampleRate);
            case 'high':
                return this.lanczoResample(inputBuffer, inputSampleRate, outputSampleRate);
            case 'good':
            default:
                // 品質と速度のバランス
                if (Math.abs(inputSampleRate - outputSampleRate) / outputSampleRate < 0.1) {
                    // 10%未満の差の場合は線形補間
                    return this.linearResample(inputBuffer, inputSampleRate, outputSampleRate);
                } else {
                    // 大きな差の場合はランチョス補間
                    return this.lanczoResample(inputBuffer, inputSampleRate, outputSampleRate);
                }
        }
    }

    /**
     * 音声データを16kHz/16bitに変換
     * @param {Float32Array} inputBuffer - 入力音声データ
     * @param {number} inputSampleRate - 入力サンプリングレート
     * @param {string} quality - リサンプリング品質
     * @returns {ArrayBuffer} - 16kHz/16bit PCMデータ
     */
    convertToWhisperFormat(inputBuffer, inputSampleRate, quality = 'good') {
        // Step 1: リサンプリング（必要な場合）
        let processedBuffer = inputBuffer;
        if (inputSampleRate !== this.targetSampleRate) {
            processedBuffer = this.resample(inputBuffer, inputSampleRate, this.targetSampleRate, quality);
        }

        // Step 2: 16bit PCM に変換
        const int16Buffer = this.float32To16BitPCM(processedBuffer);
        
        // Step 3: ArrayBuffer として返す
        return int16Buffer.buffer;
    }

    /**
     * Web Audio APIの制約を考慮した最適なサンプリングレート取得
     * @param {number} desiredSampleRate - 希望サンプリングレート
     * @returns {number} - 実際に使用するサンプリングレート
     */
    getOptimalSampleRate(desiredSampleRate = this.targetSampleRate) {
        // 一般的なサンプリングレート
        const commonRates = [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 96000];
        
        // 最も近いサンプリングレートを探す
        let closest = commonRates[0];
        let minDiff = Math.abs(desiredSampleRate - closest);
        
        for (const rate of commonRates) {
            const diff = Math.abs(desiredSampleRate - rate);
            if (diff < minDiff) {
                minDiff = diff;
                closest = rate;
            }
        }
        
        return closest;
    }

    /**
     * 音声データの統計情報を取得
     * @param {Float32Array} buffer - 音声データ
     * @returns {Object} - 統計情報
     */
    getAudioStats(buffer) {
        let min = Infinity;
        let max = -Infinity;
        let sum = 0;
        let sumSquares = 0;

        for (let i = 0; i < buffer.length; i++) {
            const sample = buffer[i];
            min = Math.min(min, sample);
            max = Math.max(max, sample);
            sum += sample;
            sumSquares += sample * sample;
        }

        const mean = sum / buffer.length;
        const variance = (sumSquares / buffer.length) - (mean * mean);
        const rms = Math.sqrt(sumSquares / buffer.length);

        return {
            length: buffer.length,
            min,
            max,
            mean,
            variance,
            rms,
            dynamic_range: max - min
        };
    }
}

// リアルタイム音声処理用のバッファ管理クラス
class AudioBufferManager {
    constructor(converter, targetChunkSize = 1024) {
        this.converter = converter;
        this.targetChunkSize = targetChunkSize;
        this.buffer = [];
        this.inputSampleRate = 44100; // デフォルト値
    }

    setInputSampleRate(sampleRate) {
        this.inputSampleRate = sampleRate;
        console.log(`Input sample rate set to: ${sampleRate}Hz`);
    }

    /**
     * 音声チャンクを追加し、必要に応じて変換済みデータを返す
     * @param {Float32Array} chunk - 音声チャンク
     * @returns {ArrayBuffer|null} - 変換済みデータまたはnull
     */
    addChunk(chunk) {
        // バッファに追加
        this.buffer.push(...chunk);

        // 十分なデータが蓄積されたら処理
        if (this.buffer.length >= this.targetChunkSize) {
            const processChunk = new Float32Array(this.buffer.splice(0, this.targetChunkSize));
            return this.converter.convertToWhisperFormat(processChunk, this.inputSampleRate);
        }

        return null;
    }

    /**
     * 残りのバッファをフラッシュ
     * @returns {ArrayBuffer|null} - 残りの変換済みデータまたはnull
     */
    flush() {
        if (this.buffer.length > 0) {
            const remaining = new Float32Array(this.buffer);
            this.buffer = [];
            return this.converter.convertToWhisperFormat(remaining, this.inputSampleRate);
        }
        return null;
    }

    clear() {
        this.buffer = [];
    }
}

// エクスポート（Node.js環境での使用を想定）
// ブラウザ 版
export { AudioConverter, AudioBufferManager };

// Node.js 版
// if (typeof module !== 'undefined' && module.exports) {
//     module.exports = { AudioConverter, AudioBufferManager };
// }
