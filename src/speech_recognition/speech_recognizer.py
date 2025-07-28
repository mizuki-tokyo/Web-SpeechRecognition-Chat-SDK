import torch
import numpy as np
import whisper
import inspect, asyncio
import uuid
from enum import Enum
from itertools import islice
import logging

from .audio_log_config import AudioLogConfig
from .vad_config import VADConfig
from .audio_logger import AudioLogger
from .whisper_processor import WhisperProcessor
from .numpy_ring_buffer import NumPyRingBuffer

logger = logging.getLogger(__name__)


class Meta(type):
    _vad_config = VADConfig()
    _audio_log_config = AudioLogConfig()
    _audio_logger = AudioLogger(_audio_log_config)

    @property
    def vad_config(cls):
        return cls._vad_config

    @property
    def audio_log_config(cls):
        return cls._audio_log_config

    class TargetConfig(Enum):
        VAD = 1
        AUDIO_LOG = 2
        ALL = 3

    def load_config(cls, target=TargetConfig.ALL):
        if target == cls.TargetConfig.VAD:
            cls._vad_config.load_config()
        elif target == cls.TargetConfig.AUDIO_LOG:
            cls._audio_log_config.load_config()
        else:
            cls._vad_config.load_config()
            cls._audio_log_config.load_config()

    def save_config(cls, target=TargetConfig.ALL):
        if target == TargetConfig.VAD:
            cls._vad_config.save_config()
        elif target == TargetConfig.AUDIO_LOG:
            cls._audio_log_config.save_config()
        else:
            cls._vad_config.save_config()
            cls._audio_log_config.save_config()


##########################################
# SpeechRecognizer class
##########################################
class SpeechRecognizer(metaclass=Meta):

    class State(Enum):
        SPEECH_START = 1
        SPEECH_END = 2
        RECOGNITION_RESULT = 3

    _vad_model = None

    @classmethod
    def is_vad_model_loaded(cls):
        return cls._vad_model is not None

    @staticmethod
    def is_whisper_model_loaded():
        return WhisperProcessor.is_model_loaded()

    def __init__(self, session_id, callback, running_loop):
        self._session_id = session_id
        self._speech_id = None

        self._sample_rate = 16000
        self._whisper_processor = WhisperProcessor.create()
        self._prompt = None
        
        vad_config = SpeechRecognizer.vad_config;
        self._chunk_size = vad_config.chunk_size
        self._min_speech_duration_s = vad_config.min_speech_duration_s
        self._max_speech_duration_s = vad_config.max_speech_duration_s
        self._prefix_speech_pad_s = vad_config.prefix_speech_pad_s
        self._silence_duration_frames = int((self._sample_rate * vad_config.silence_duration_ms) / (self._chunk_size * 1000))

        audio_buffer_sec = vad_config.max_speech_duration_s + vad_config.prefix_speech_pad_s + vad_config.silence_duration_s
        self._audio_buffer = NumPyRingBuffer(maxsize=int(self._sample_rate*audio_buffer_sec), dtype=np.float32)
        self._chunk_buffer = NumPyRingBuffer(self._chunk_size, dtype=np.float32)
        self._silence_counter = 0
        self._speech_start_index = -1

        self._callback = callback
        self._running_loop = running_loop


    @property
    def language(self):
        return self._whisper_processor.language

    @language.setter
    def language(self, value):
        # if not value:
        #     raise ValueError("Language value is empty")
        if value == "":
            value = None # auto detection
        elif not isinstance(value, str):
            value = None # auto detection
            logger.warn(f"Invalid language value: {value}")
        if self._whisper_processor:
            self._whisper_processor.language = value

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, value):
        if value == "":
            value = None
        elif not isinstance(value, str):
            value = None # auto detection
            logger.warn(f"Invalid prompt value: {value}")
            self._prompt = value

    def add_audio_chunk(self, audio_data):
        # データ形式を判定して処理
        if len(audio_data) % 4 == 0:
            # Float32 配列として解釈を試行
            try:
                float32_array = np.frombuffer(audio_data, dtype=np.float32)
                # 妥当な範囲チェック（Float32 は通常 -1.0〜1.0）
                if np.all(np.abs(float32_array) <= 1.5):  # 少し余裕を持たせる
                    # Float32 として処理
                    logger.debug(f"Received Float32 data: {len(float32_array)} samples")
                    self._audio_buffer.put_bulk(float32_array)
                    # VAD、および、音声認識を実行
                    self._process_audio(float32_array)
                    return

            except (ValueError, OverflowError):
                # Float32 では無かった
                pass

        # 16bit PCM として処理
        int16_array = np.frombuffer(audio_data, dtype=np.int16)
        logger.debug(f"Received 16bit PCM data: {len(int16_array)} samples")
        # Float32 に変換 (-1.0 to 1.0)
        float32_array = int16_array.astype(np.float32) / 32768.0
        self._audio_buffer.put_bulk(float32_array)
            
        # VAD、および、音声認識を実行
        self._process_audio(float32_array)


    def _notify(self, state):
        if inspect.iscoroutinefunction(self._callback):
            coroutine = self._callback(state, self._session_id, self._speech_id, self._audio_buffer.size())
            asyncio.create_task(coroutine)  # あるいは asyncio.run(coroutine)
        else:
            self._callback(state, self._session_id, self._speech_id, self._audio_buffe.size())


    def _process_audio(self, audio_array):
        if not SpeechRecognizer._vad_model or len(audio_array) == 0:
            return

        # バッファ内に未処理の音声データが存在する場合、
        # 未処理の音声データと要求された音声データとを結合する
        count = self._chunk_buffer.size()
        if count > 0:
            audio_array = np.concatenate((self._chunk_buffer.get_bulk(count), audio_array))
            self._chunk_buffer.clear()

        # 音声データをチャンクサイズごとに切り出して処理する
        start = 0
        remain = len(audio_array)
        while remain >= self._chunk_size:
            self._process_audio_chunk(audio_array[start:start+self._chunk_size])
            start += self._chunk_size
            remain -= self._chunk_size

        # 未処理の音声データが存在する場合、バッファに入れる
        if remain > 0:
            self._chunk_buffer.put_bulk(audio_array[start:])


    def _process_audio_chunk(self, audio_chunk):
        """音声を処理して VAD 判定を行う"""

        # 音声データの統計をログ記録
        if logger.isEnabledFor(logging.DEBUG):
            rms = np.sqrt(np.mean(audio_chunk**2))
            logger.debug(f"Audio RMS: {rms:.4f}, Buffer size: {len(audio_chunk)}")

        # VAD 実行
        try:
            speech_prob = SpeechRecognizer._vad_model(torch.from_numpy(audio_chunk), self._sample_rate).item()
            # 設定可能な閾値を使用
            is_speech = speech_prob > SpeechRecognizer.vad_config.threshold
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Speech probability: {speech_prob:.3f}, Is speech: {is_speech}, Threshold: {SpeechRecognizer.vad_config.threshold}")

            if is_speech:
                if self._speech_start_index < 0:
                    self._speech_id = str(uuid.uuid4())
                    self._speech_start_index = max(0, self._audio_buffer.size() - int(self._sample_rate * self._prefix_speech_pad_s))

                    logger.info(f"Speech started for session {self._session_id} (prob: {speech_prob:.3f})")
                    self._notify(SpeechRecognizer.State.SPEECH_START)

                self._silence_counter = 0

            else:
                if self._speech_start_index >= 0:
                    self._silence_counter += 1
                    if self._silence_counter >= self._silence_duration_frames:
                        logger.info(f"Speech ended for session {self._session_id} (silence frames: {self._silence_counter})")

                        self._audio_buffer.get_bulk(self._speech_start_index) # 読み飛ばす
                        speech_array = self._audio_buffer.get_bulk(self._audio_buffer.size())
                        
                        # 音声認識を実行
                        self._trigger_recognition(speech_array)

                        self._silence_counter = 0
                        self._audio_buffer.clear()
                        self._speech_start_index = -1
                        self._chunk_buffer.clear()
                        self._notify(SpeechRecognizer.State.SPEECH_END)

                        self._speech_id = None # Must be after _notify() has been called
                    
        except Exception as e:
            logger.error(f"VAD processing error: {e}")


    def _trigger_recognition(self, speech_array):
        """音声認識をトリガー"""

        if not self._whisper_processor or len(speech_array) == 0:
            return
        
        try:
            # 設定可能な最小長チェック
            min_length = self._sample_rate * self._min_speech_duration_s
            if len(speech_array) < min_length:
                logger.info(f"Speech too short ({len(speech_array)} samples < {min_length:.0f}), skipping recognition")
                return

            # 最大長チェック
            max_length = self._sample_rate * self._max_speech_duration_s
            if len(speech_array) > max_length:
                logger.info(f"Speech too long ({len(speech_array)} samples > {max_length:.0f}), truncating")
                speech_array = speech_array[:int(max_length)]
                
            logger.info(f"Triggering recognition for {len(speech_array)} samples ({len(speech_array)/self._sample_rate:.2f}s)")
            
            # 音声ログを保存
            if SpeechRecognizer.audio_log_config.enabled:
                log_file = SpeechRecognizer._audio_logger.save_audio_raw(speech_array, self._session_id)
                if log_file:
                    logger.info(f"Audio log saved for session {self._session_id}: {log_file}")
                    
            # 非同期で音声認識を実行
            self._whisper_processor.recognize_async(
                speech_array, 
                self._session_id,
                self._speech_id,
                lambda result, session_id, speech_id : self._callback(
                    SpeechRecognizer.State.RECOGNITION_RESULT, session_id, speech_id, result
                ),
                self._running_loop,
                self._prompt
            )

        except Exception as e:
            logger.error(f"Failed to trigger recognition: {e}")


##########################################
# silero VAD モデルをロード
##########################################
## キャッシュが存在しない場合、GitHub から最新バージョンをダウンロード（source='github'）
## ダウンロードした内容は ~/.cache/torch/hub/... にキャッシュされる
try:
    SpeechRecognizer._vad_model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False, # キャッシュしたモデルが存在すれば、それを使用する
        onnx=False
    )
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    logger.info("Silero VAD model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load Silero VAD model: {e}")
    SpeechRecognizer._vad_model = None


SpeechRecognizer.load_config()
