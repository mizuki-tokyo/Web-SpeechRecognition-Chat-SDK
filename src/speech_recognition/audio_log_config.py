import logging
import json
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 音声ログ設定
class AudioLogConfig:
    def __init__(self):
        self.enabled = True  # 音声ログ出力の有効/無効
        self.output_dir = "audio_logs"  # 出力ディレクトリ
        self.max_files = 1000  # 最大ファイル数（古いファイルを自動削除）
        self.config_file = "config/audio-log-config.json"

    def ensure_output_dir(self):
        """出力ディレクトリが存在することを確認"""
        if self.enabled:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def load_config(self):
        """設定ファイルから設定を読み込む"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                self.enabled = config_data.get('enabled', self.enabled)
                self.output_dir = config_data.get('output_dir', self.output_dir)
                self.max_files = config_data.get('max_files', self.max_files)
                
                logger.info(f"Audio log configuration loaded from {self.config_file}")
                return True
            else:
                logger.info(f"Audio log config file {self.config_file} not found, using defaults")
                # デフォルト設定を保存
                self.save_config()
                return False
                
        except Exception as e:
            logger.error(f"Failed to load VAD configuration: {e}")
            return False
        
    def save_config(self):
        """設定をファイルに保存する"""
        try:
            config_data = {
                'enabled': self.enabled,
                'output_dir': self.output_dir,
                'max_files': self.max_files,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"audio log configuration saved to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio log configuration: {e}")
            return False


    # def cleanup_old_files(self):
    #     """古いファイルをクリーンアップ"""
    #     if not self.enabled:
    #         return
            
    #     try:
    #         output_path = Path(self.output_dir)
    #         if not output_path.exists():
    #             return
                
    #         # ファイル一覧を取得（作成日時順）
    #         files = sorted(output_path.glob("*.raw"), key=lambda x: x.stat().st_ctime)
            
    #         # 最大ファイル数を超えている場合、古いファイルを削除
    #         if len(files) > self.max_files:
    #             files_to_delete = files[:-self.max_files]
    #             for file_path in files_to_delete:
    #                 try:
    #                     file_path.unlink()
    #                     logger.info(f"Deleted old audio log file: {file_path}")
    #                 except Exception as e:
    #                     logger.error(f"Failed to delete file {file_path}: {e}")

    #     except Exception as e:
    #         logger.error(f"Cleanup error: {e}")


