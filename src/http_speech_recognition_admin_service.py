
import numpy as np
import json
import logging
import io
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from speech_recognition import SpeechRecognizer

logger = logging.getLogger(__name__)

class HttpSpeechRecognitionAdminService:

    active_sessions = None

    @staticmethod
    def get_vad_config():
        """VAD 設定を取得"""
        return {
            "config": SpeechRecognizer.vad_config.to_dict(),
            "descriptions": {
                "threshold": "Speech detection confidence threshold (0.0–1.0)",
                "min_speech_duration_ms": "Ignore speech shorter than this (ms)",
                "max_speech_duration_s": "Cut speech longer than this (sec)",
                "prefix_speech_pad_ms": "Helps prevents cutting off beginning of speech (ms)",
                "silence_duration_ms": "Speech considered finished after this silence",
                "chunk_size": "Number of samples per process (32ms@16kHz=512)"
            }
        }

    @classmethod
    def update_vad_config(cls, config: dict):
        """VAD 設定を更新"""
        vad_config = SpeechRecognizer.vad_config
        try:
            old_config = vad_config.to_dict()
            vad_config.update_from_dict(config)
            new_config = vad_config.to_dict()
            
            # 設定をファイルに保存
            vad_config.save_config()
            logger.info(f"VAD configuration updated and saved: {old_config} -> {new_config}")
        
            return {
                "status": "success",
                "message": "VAD configuration updated and saved",
                "old_config": old_config,
                "new_config": new_config,
                "active_sessions_updated": len(cls.active_sessions)
            }
        except Exception as e:
            logger.error(f"Failed to update VAD config: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @classmethod
    def reset_vad_config(cls):
        """VAD 設定をデフォルトにリセット"""
        vad_config = SpeechRecognizer.vad_config
        try:
            old_config = vad_config.to_dict()
            # VAD 設定をリセット
            vad_config.reset()
            # 設定をファイルに保存
            vad_config.save_config()
            logger.info(f"VAD configuration reset to defaults and saved")

            return {
                "status": "success",
                "message": "VAD configuration reset to defaults and saved",
                "old_config": old_config,
                "new_config": vad_config.to_dict(),
                "active_sessions_updated": len(cls.active_sessions)
            }
        except Exception as e:
            logger.error(f"Failed to reset VAD config: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_audio_log_config():
        """音声ログ設定を取得"""
        audio_log_config = SpeechRecognizer.audio_log_config
        return {
            "enabled": audio_log_config.enabled,
            "output_dir": audio_log_config.output_dir,
            "max_files": audio_log_config.max_files
        }


    @staticmethod
    def update_audio_log_config(config: dict):
        """音声ログ設定を更新"""
        audio_log_config = SpeechRecognizer.audio_log_config

        try:
            if "enabled" in config:
                audio_log_config.enabled = bool(config["enabled"])
                logger.info(f"Audio logging {'enabled' if audio_log_config.enabled else 'disabled'}")

            if "output_dir" in config:
                audio_log_config.output_dir = str(config["output_dir"])
                audio_log_config.ensure_output_dir()
                logger.info(f"Audio log directory changed to: {audio_log_config.output_dir}")

            if "max_files" in config:
                audio_log_config.max_files = int(config["max_files"])
                logger.info(f"Audio log max files set to: {audio_log_config.max_files}")

            # 設定をファイルに保存
            audio_log_config.save_config()

            return {
                "status": "success",
                "message": "Audio log configuration updated and saved",
                "config": {
                    "enabled": audio_log_config.enabled,
                    "output_dir": audio_log_config.output_dir,
                    "max_files": audio_log_config.max_files
                }
            }
        except Exception as e:
            logger.error(f"Failed to update audio log config: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


    @staticmethod
    def list_audio_logs():
        """音声ログファイル一覧を取得"""
        audio_log_config = SpeechRecognizer.audio_log_config

        try:
            if not audio_log_config.enabled:
                return {"error": "Audio logging is disabled"}

            output_path = Path(audio_log_config.output_dir)
            if not output_path.exists():
                return {"files": [], "total": 0}

            # RAW ファイルのみ取得
            raw_files = list(output_path.glob("*.raw"))

            file_info = []
            for file_path in sorted(raw_files, key=lambda x: x.stat().st_ctime, reverse=True):
                try:
                    stat = file_path.stat()
                    meta_file = file_path.with_suffix('.meta')

                    info = {
                        "filename": file_path.name,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "has_metadata": meta_file.exists()
                    }

                    # メタデータがあれば読み込み
                    if meta_file.exists():
                        try:
                            with open(meta_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                                info.update({
                                    "session_id": metadata.get("session_id"),
                                    "duration_seconds": metadata.get("duration_seconds"),
                                    "samples": metadata.get("samples"),
                                    "sample_rate": metadata.get("sample_rate")
                                })
                        except Exception as e:
                            logger.warning(f"Failed to read metadata for {file_path}: {e}")

                    file_info.append(info)

                except Exception as e:
                    logger.error(f"Failed to get info for {file_path}: {e}")

            return {
                "files": file_info,
                "total": len(file_info),
                "total_size_bytes": sum(f["size_bytes"] for f in file_info)
            }

        except Exception as e:
            logger.error(f"Failed to list audio logs: {e}")
            return {"error": str(e)}


    @staticmethod
    def play_audio_file(filename: str):
        """音声ログファイルを WAV 形式で配信"""
        audio_log_config = SpeechRecognizer.audio_log_config

        try:
            if not audio_log_config.enabled:
                raise HTTPException(status_code=403, detail="Audio logging is disabled")

            # ファイル名の検証（セキュリティ対策）
            if not filename.endswith('.raw') or '..' in filename or '/' in filename:
                raise HTTPException(status_code=400, detail="Invalid filename")

            raw_file_path = Path(audio_log_config.output_dir) / filename
            meta_file_path = raw_file_path.with_suffix('.meta')

            if not raw_file_path.exists():
                raise HTTPException(status_code=404, detail="Audio file not found")

            # メタデータを読み込み
            sample_rate = 16000  # デフォルト値
            if meta_file_path.exists():
                try:
                    with open(meta_file_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        sample_rate = metadata.get('sample_rate', 16000)
                except Exception as e:
                    logger.warning(f"Failed to read metadata: {e}")

            # RAW ファイルを読み込み
            audio_data = np.fromfile(raw_file_path, dtype=np.float32)
            logger.info(f"Loaded audio data: {len(audio_data)} samples, sample_rate: {sample_rate}")

            if len(audio_data) == 0:
                raise HTTPException(status_code=400, detail="Empty audio file")

            # 音声データの範囲をチェック
            logger.info(f"Audio data range: min={np.min(audio_data):.4f}, max={np.max(audio_data):.4f}")

            try:
                # Float32 を 16bit PCM に変換
                # -1.0～1.0 の範囲を-32768～32767 にマップ
                audio_clipped = np.clip(audio_data, -1.0, 1.0)
                audio_int16 = (audio_clipped * 32767).astype(np.int16)

                logger.info(f"Converted to 16bit PCM: {len(audio_int16)} samples")
                logger.info(f"PCM range: min={np.min(audio_int16)}, max={np.max(audio_int16)}")

                # WAV ファイルを手動で構築（より確実な Safari 対応）
                pcm_data = audio_int16.tobytes()
                pcm_length = len(pcm_data)

                # WAV ヘッダーを手動構築
                header = bytearray()

                # RIFF ヘッダー
                header.extend(b'RIFF')  # ChunkID
                header.extend((36 + pcm_length).to_bytes(4, 'little'))  # ChunkSize
                header.extend(b'WAVE')  # Format

                # fmt チャンク
                header.extend(b'fmt ')  # Subchunk1ID
                header.extend((16).to_bytes(4, 'little'))  # Subchunk1Size (PCM = 16)
                header.extend((1).to_bytes(2, 'little'))   # AudioFormat (PCM = 1)
                header.extend((1).to_bytes(2, 'little'))   # NumChannels (mono = 1)
                header.extend(sample_rate.to_bytes(4, 'little'))  # SampleRate
                header.extend((sample_rate * 2).to_bytes(4, 'little'))  # ByteRate (SampleRate * NumChannels * BitsPerSample/8)
                header.extend((2).to_bytes(2, 'little'))   # BlockAlign (NumChannels * BitsPerSample/8)
                header.extend((16).to_bytes(2, 'little'))  # BitsPerSample

                # data チャンク
                header.extend(b'data')  # Subchunk2ID
                header.extend(pcm_length.to_bytes(4, 'little'))  # Subchunk2Size

                # 完全な WAV ファイル
                wav_content = bytes(header) + pcm_data

                logger.info(f"WAV file created successfully: {len(wav_content)} bytes")
                logger.info(f"WAV header verification: {wav_content[:4]} (should be b'RIFF')")
                logger.info(f"WAV format verification: {wav_content[8:12]} (should be b'WAVE')")

                # WAV ファイルとして返す
                return StreamingResponse(
                    io.BytesIO(wav_content),
                    media_type="audio/wav",
                    headers={
                        "Content-Disposition": f"inline; filename=\"{filename.replace('.raw', '.wav')}\"",
                        "Content-Length": str(len(wav_content)),
                        "Cache-Control": "no-cache",
                        "Accept-Ranges": "bytes",
                        "Access-Control-Allow-Origin": "*"  # CORS対応
                    }
                )

            except Exception as wav_error:
                logger.error(f"WAV conversion error: {wav_error}")
                raise HTTPException(status_code=500, detail=f"WAV conversion failed: {wav_error}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to serve audio file {filename}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


    @staticmethod
    def get_audio_file_info(filename: str):
        """音声ログファイルの詳細情報を取得（デバッグ用）"""

        audio_log_config = SpeechRecognizer.audio_log_config

        try:
            if not audio_log_config.enabled:
                raise HTTPException(status_code=403, detail="Audio logging is disabled")

            # ファイル名の検証
            if not filename.endswith('.raw') or '..' in filename or '/' in filename:
                raise HTTPException(status_code=400, detail="Invalid filename")

            raw_file_path = Path(audio_log_config.output_dir) / filename
            meta_file_path = raw_file_path.with_suffix('.meta')

            if not raw_file_path.exists():
                raise HTTPException(status_code=404, detail="Audio file not found")

            # RAW ファイルを読み込み
            audio_data = np.fromfile(raw_file_path, dtype=np.float32)

            # メタデータを読み込み
            metadata = {}
            if meta_file_path.exists():
                try:
                    with open(meta_file_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read metadata: {e}")

            # ファイル統計情報
            file_stats = raw_file_path.stat()

            # 音声データ統計
            audio_stats = {
                "samples": len(audio_data),
                "duration_seconds": len(audio_data) / metadata.get('sample_rate', 16000),
                "min_value": float(np.min(audio_data)) if len(audio_data) > 0 else 0,
                "max_value": float(np.max(audio_data)) if len(audio_data) > 0 else 0,
                "mean_value": float(np.mean(audio_data)) if len(audio_data) > 0 else 0,
                "rms_value": float(np.sqrt(np.mean(audio_data**2))) if len(audio_data) > 0 else 0
            }

            return {
                "filename": filename,
                "file_size_bytes": file_stats.st_size,
                "expected_samples": file_stats.st_size // 4,  # Float32 = 4 bytes per sample
                "metadata": metadata,
                "audio_stats": audio_stats,
                "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "is_valid": len(audio_data) > 0 and file_stats.st_size % 4 == 0
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get audio file info {filename}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


    @staticmethod
    def download_audio_file(filename: str):
        """音声ログファイルをダウンロード（RAW 形式）"""

        audio_log_config = SpeechRecognizer.audio_log_config

        try:
            if not audio_log_config.enabled:
                raise HTTPException(status_code=403, detail="Audio logging is disabled")

            # ファイル名の検証
            if not filename.endswith('.raw') or '..' in filename or '/' in filename:
                raise HTTPException(status_code=400, detail="Invalid filename")

            file_path = Path(audio_log_config.output_dir) / filename

            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            return FileResponse(
                file_path,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to download file {filename}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

