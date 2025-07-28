# FastAPI + Silero VAD + Whisper 音声認識サーバ

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse

import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
from dotenv import load_dotenv, set_key

LOG_FORMAT = "%(asctime)s %(levelname)-5s %(message)s (%(name)-12s)"

# config ディレクトリ作成
Path("config").mkdir(parents=True, exist_ok=True)

############################################################
class AppConfig:
    _env_path = Path("config/app-config.env")
    log_level = "DEBUG"
    whisper_model = "large-v3" #"base"

    @classmethod
    def load(cls):
        load_dotenv(dotenv_path=cls._env_path, override=True)
        cls.log_level = os.getenv("LOG_LEVEL")
        cls.whisper_model = os.getenv("WHISPER_MODEL")
    @classmethod
    def save(cls):
        set_key(dotenv_path=cls._env_path, key_to_set="LOG_LEVEL", value_to_set=cls.log_level)
        set_key(dotenv_path=cls._env_path, key_to_set="WHISPER_MODEL", value_to_set=cls.whisper_model)

# 設定ファイル読み込み
AppConfig.load()

# Whisper モデルを指定
WHISPER_MODEL = AppConfig.whisper_model

# ログレベルを設定
try:
    logging.basicConfig(
        level=AppConfig.log_level,
        format=LOG_FORMAT,
        datefmt='%y-%m-%d %H:%M'
    )
    # root = logging.getLogger()
    # handler = TimedRotatingFileHandler(
    #     'log/server.log',
    #     when='midnight',  # 毎日深夜にローテート
    #     interval=1,
    #     backupCount=7     # 直近 7 日分を保持
    # )
    # root.addHandler(handler)
except:
    print(f"ERROR: Log level '{AppConfig.log_level}' is invalid.")
    logging.basicConfig(level=logging.INFO)
    AppConfig.log_level = logging.INFO

############################################################

# ログオブジェクトを作成
logger = logging.getLogger(__name__)

# セッション管理オブジェクトを作成 (プロダクション環境では DB 使用を推奨)
active_sessions = {}

# FastAPI オブジェクトを作成
app = FastAPI(title="Audio Recognition Server", version="1.0.0")


logger.info(f"Whisper model is '{WHISPER_MODEL}'")

############################################################
# Sample web site
############################################################

# 静的ファイルをマウント
app.mount("/public", StaticFiles(directory="public", html=True), name="public")
app.mount("/js", StaticFiles(directory="public/js", html=True), name="public/js")
app.mount("/css", StaticFiles(directory="public/css", html=True), name="public/css")

@app.get("/")
async def read_index():
    return FileResponse('public/index.html')

@app.get("/admin")
async def admin_page():
    """管理画面"""
    return FileResponse('public/admin.html')


############################################################
# Web API endpoints for speech recognition
############################################################
from src.http_speech_recognition_service import HttpSpeechRecognitionService
HttpSpeechRecognitionService.active_sessions = active_sessions
HttpSpeechRecognitionService.continuous_recognition = True # False: auto session close

@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    await HttpSpeechRecognitionService.websocket_audio_endpoint(websocket)


@app.get("/health")
def health_check():
    return HttpSpeechRecognitionService.health_check()


@app.get("/continuous", response_class=PlainTextResponse)
def is_continuous():
    return "true" if HttpSpeechRecognitionService.continuous_recognition else "false"

############################################################
# Web API endpoints for administration
############################################################
from src.http_speech_recognition_admin_service import HttpSpeechRecognitionAdminService
HttpSpeechRecognitionAdminService.active_sessions = active_sessions


@app.get("/config/vad")
def get_vad_config():
    """VAD 設定を取得"""
    return HttpSpeechRecognitionAdminService.get_vad_config()


@app.post("/config/vad")
def update_vad_config(config: dict):
    """VAD 設定を更新"""
    return HttpSpeechRecognitionAdminService.update_vad_config(config)


@app.post("/config/vad/reset")
def reset_vad_config():
    """VAD 設定をデフォルトにリセット"""
    return HttpSpeechRecognitionAdminService.reset_vad_config()


@app.get("/config/audio-log")
def get_audio_log_config():
    """音声ログ設定を取得"""
    return HttpSpeechRecognitionAdminService.get_audio_log_config()


@app.post("/config/audio-log")
def update_audio_log_config(config: dict):
    """音声ログ設定を更新"""
    return HttpSpeechRecognitionAdminService.update_audio_log_config(config)


@app.get("/logs/audio/list")
def list_audio_logs():
    """音声ログファイル一覧を取得"""
    return HttpSpeechRecognitionAdminService.list_audio_logs()


@app.get("/logs/audio/play/{filename}")
def play_audio_file(filename: str):
    """音声ログファイルを WAV 形式で配信"""
    return HttpSpeechRecognitionAdminService.play_audio_file(filename)


@app.get("/logs/audio/info/{filename}")
def get_audio_file_info(filename: str):
    """音声ログファイルの詳細情報を取得（デバッグ用）"""
    return HttpSpeechRecognitionAdminService.get_audio_file_info(filename)


@app.get("/logs/audio/download/{filename}")
def download_audio_file(filename: str):
    """音声ログファイルをダウンロード（RAW 形式）"""
    return HttpSpeechRecognitionAdminService.download_audio_file(filename)



############################################################
if __name__ == "__main__":
    import uvicorn

    try:
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = LOG_FORMAT
    except:
        pass

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,
        log_level=None#AppConfig.log_level
    )
