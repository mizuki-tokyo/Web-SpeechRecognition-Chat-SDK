import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Silero VAD 設定
class VADConfig:
    def __init__(self):
        self.threshold = 0.5        # 音声判定閾値 (0.0-1.0)
        self.min_speech_duration_ms = 250    # 最小音声持続時間 (ms)
        self.max_speech_duration_s = 30.0    # 最大音声持続時間 (秒)
        self.prefix_speech_pad_ms = 300  # 音声前のパディング (ms)
        self.silence_duration_ms = 500   # 無音の最大継続時間（ms）
        self.chunk_size = 512       # 処理チャンクサイズ（サンプル数）
        self.config_file = "config/vad-config.json"

    @property
    def min_speech_duration_s(self):
        return self.min_speech_duration_ms / 1000

    @property
    def prefix_speech_pad_s(self):
        return self.prefix_speech_pad_ms / 1000

    @property
    def silence_duration_s(self):
        return self.silence_duration_ms / 1000

    def reset(self):
        self.__init__()
        
    def to_dict(self):
        """設定を辞書形式で返す"""
        return {
            "threshold": self.threshold,
            "min_speech_duration_ms": self.min_speech_duration_ms,
            "max_speech_duration_s": self.max_speech_duration_s,
            "prefix_speech_pad_ms": self.prefix_speech_pad_ms,
            "silence_duration_ms": self.silence_duration_ms,
            "chunk_size": self.chunk_size
        }

    def load_config(self):
        """設定ファイルから設定を読み込む"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                self.threshold = config_data.get('threshold', self.threshold)
                self.min_speech_duration_ms = config_data.get('min_speech_duration_ms', self.min_speech_duration_ms)
                self.max_speech_duration_s = config_data.get('max_speech_duration_s', self.max_speech_duration_s)
                self.prefix_speech_pad_ms = config_data.get('prefix_speech_pad_ms', self.prefix_speech_pad_ms)
                self.silence_duration_ms = config_data.get('silence_duration_ms', self.silence_duration_ms)
                self.chunk_size = config_data.get('chunk_size', self.chunk_size)

                logger.info(f"VAD configuration loaded from {self.config_file}")
                return True
            else:
                logger.info(f"VAD config file {self.config_file} not found, using defaults")
                # デフォルト設定を保存
                self.save_config()
                return False
                
        except Exception as e:
            logger.error(f"Failed to load VAD configuration: {e}")
            return False
        
    def update_from_dict(self, config_dict):
        """辞書から設定を更新"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                # 型チェックと範囲チェック
                if key == "threshold":
                    self.threshold = max(0.0, min(1.0, float(value)))
                elif key in ["min_speech_duration_ms", "prefix_speech_pad_ms", "silence_duration_ms"]:
                    setattr(self, key, max(0, int(value)))
                elif key == "max_speech_duration_s":
                    self.max_speech_duration_s = max(0.1, float(value))
                elif key in ["chunk_size"]:
                    setattr(self, key, max(1, int(value)))
                elif key in ["activation_threshold"]:
                    setattr(self, key, max(0.0, float(1.0)))

    def save_config(self):
        """設定をファイルに保存する"""
        try:
            config_data = {
                'threshold': self.threshold,
                'min_speech_duration_ms': self.min_speech_duration_ms,
                'max_speech_duration_s': self.max_speech_duration_s,
                'speech_pad_ms': self.speech_pad_ms,
                'silence_duration_ms': self.silence_duration_ms,
                'chunk_size': self.chunk_size,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info(f"VAD configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save VAD configuration: {e}")
            return False
