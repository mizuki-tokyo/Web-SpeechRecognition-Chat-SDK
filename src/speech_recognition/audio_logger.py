from pathlib import Path
import json
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AudioLogger:
    def __init__(self, config):
        self.config = config
        self.sample_rate = 16000
        
    def save_audio_raw(self, audio_data, session_id):
        """音声データを RAW 形式で保存"""
        if not self.config.enabled:
            return None
            
        try:
            # ファイル名生成（タイムスタンプ + セッション ID）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ミリ秒まで
            filename = f"audio_{timestamp}_session_{session_id}.raw"
            filepath = Path(self.config.output_dir) / filename
            
            # 音声データを numpy 配列として準備
            if isinstance(audio_data, list):
                audio_array = np.array(audio_data, dtype=np.float32)
            else:
                audio_array = audio_data.astype(np.float32)
                
            # RAW 形式で保存（Float32 little-endian）
            audio_array.tobytes('C')  # メモリレイアウトを確認
            with open(filepath, 'wb') as f:
                f.write(audio_array.tobytes())
                
            # メタデータファイルも保存（オプション）
            meta_filepath = filepath.with_suffix('.meta')
            metadata = {
                "filename": filename,
                "session_id": session_id,
                "timestamp": timestamp,
                "sample_rate": self.sample_rate,
                "channels": 1,
                "data_type": "float32",
                "duration_seconds": len(audio_array) / self.sample_rate,
                "samples": len(audio_array)
            }
            
            with open(meta_filepath, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Audio log saved: {filepath} ({len(audio_array)} samples, {len(audio_array)/self.sample_rate:.2f}s)")
            
            # クリーンアップを定期的に実行
            if np.random.random() < 0.1:  # 10% の確率で実行
                self.cleanup_old_files()
                
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save audio log: {e}")
            return None


    def cleanup_old_files(self):
        """古いファイルをクリーンアップ"""
        if not self.config.enabled:
            return
            
        try:
            output_path = Path(self.config.output_dir)
            if not output_path.exists():
                return
                
            # ファイル一覧を取得（作成日時順）
            files = sorted(output_path.glob("*.raw"), key=lambda x: x.stat().st_ctime)
            
            # 最大ファイル数を超えている場合、古いファイルを削除
            if len(files) > self.config.max_files:
                files_to_delete = files[:-self.config.max_files]
                for file_path in files_to_delete:
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted old audio log file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
