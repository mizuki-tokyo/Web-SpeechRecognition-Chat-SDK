import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from speech_recognition import SpeechRecognizer

logger = logging.getLogger(__name__)

class HttpSpeechRecognitionService:

    active_sessions = None
    continuous_recognition = False
    receiveTimeoutSec = None

    @staticmethod
    async def _on_speech_start(websocket, session_id, speech_id, param):
        response = {
            "type": "vad_result",
            "session_id": session_id,
            "speech_id": speech_id,
            "speech_detected": True,
            "speech_ended": False,
            "buffer_size": param,
            "timestamp": asyncio.get_running_loop().time()
        }
        await websocket.send_text(json.dumps(response, ensure_ascii=False))


    @staticmethod
    async def _on_speech_end(websocket, session_id, speech_id, param):
        response = {
            "type": "vad_result",
            "session_id": session_id,
            "speech_id": speech_id,
            "speech_detected": False,
            "speech_ended": True,
            "buffer_size": param,
            "timestamp": asyncio.get_running_loop().time()
        }
        await websocket.send_text(json.dumps(response, ensure_ascii=False))


    @staticmethod
    async def _on_recognition_result(websocket, session_id, speech_id, param):
        response = {
            "type": "recognition_result",
            "session_id": session_id,
            "speech_id": speech_id,
            "result": param,
            "timestamp": asyncio.get_running_loop().time()
        }
        await websocket.send_text(json.dumps(response, ensure_ascii=False))
        logger.info(f"Recognition result sent to session {session_id}: {response['result'].get('text', 'Error')}")


    @classmethod
    async def websocket_audio_endpoint(cls, websocket: WebSocket):

        await websocket.accept()

        session_id = id(websocket)  # セッション ID として websocket の ID を使用
        logger.info(f"WebSocket connection established for session {session_id}")

        auto_close = not cls.continuous_recognition
        # if auto_close:
        #     recognition_end_event = asyncio.Event()

        closed = False
        close_requested = False

        # 音声認識のコールバック関数を定義
        async def callback(state, session_id, speech_id, param):
            """認識結果を WebSocket で送信"""
            try:
                if (websocket.client_state.name == 'CONNECTED'):
                    # 発話開始
                    if state == SpeechRecognizer.State.SPEECH_START:
                        await HttpSpeechRecognitionService._on_speech_start(websocket, session_id, speech_id, param)
                    # 発話終了
                    elif state == SpeechRecognizer.State.SPEECH_END:
                        await HttpSpeechRecognitionService._on_speech_end(websocket, session_id, speech_id, param)
                    # 音声認識終了
                    elif state == SpeechRecognizer.State.RECOGNITION_RESULT:
                        await HttpSpeechRecognitionService._on_recognition_result(websocket, session_id, speech_id, param)
                        if auto_close:
                            #recognition_end_event.set()
                            close_requested = True
                            await websocket.close()
                    else:
                        logger.error(f"Receive unknown state({state}) from SpeechRecognizer")
                else:
                    logger.warning(f"WebSocket disconnected for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to send message (state:{state}): {e}")

        # セッション専用の音声認識インスタンスを作成
        speech_recognizer = SpeechRecognizer(session_id, callback, asyncio.get_running_loop())
        cls.active_sessions[session_id] = speech_recognizer
    
        try:
            try:
                json = await asyncio.wait_for(websocket.receive_json(), timeout=cls.receiveTimeoutSec)
                langCode = json["lang"]
                prompt = json["prompt"]
            except asyncio.TimeoutError:
                raise Exception("Timeout occurred: websocket.receive_text()")
            
            logger.info(f"Received lang code is '{langCode}'")
            logger.info(f"Received prompt is '{prompt}'")

            speech_recognizer.language = langCode
            speech_recognizer.prompt = prompt

            while True:
                # バイナリデータを受信（音声データ）
                try:
                    audio_data = await asyncio.wait_for(websocket.receive_bytes(), timeout=cls.receiveTimeoutSec)
                except asyncio.TimeoutError:
                    raise Exception("Timeout occurred: websocket.receive_bytes()")

                speech_recognizer.add_audio_chunk(audio_data)

                #speech_detected, speech_ended = speech_recognizer.add_audio_chunk(audio_data)
                # if auto_close and speech_ended:
                #     await recognition_end_event.wait() # 音声認識が終了するまで待機
                #     await websocket.close()
                #     # websocket.close() only sends frames, and state transitions only occur
                #     # when websocket.receive() is executed. Therefore, unless websocket.receive() is called,
                #     # client_state remains CONNECTED. ==> managed with flag variable.
                #     closed = True

        except WebSocketDisconnect:
            logger.info(f"WebSocket connection closed for session {session_id}")
            #closed = True
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
        finally:
            # セッションクリーンアップ
            if session_id in cls.active_sessions:
                del cls.active_sessions[session_id]
            if close_requested == False and websocket.client_state.name != 'DISCONNECTED':
                await websocket.close()


    @classmethod
    def health_check(cls):
        return {
            "status": "healthy",
            "active_sessions": len(cls.active_sessions),
            "vad_model_loaded": SpeechRecognizer.is_vad_model_loaded(),
            "whisper_model_loaded": SpeechRecognizer.is_whisper_model_loaded(),
            "audio_logging_enabled": SpeechRecognizer.audio_log_config.enabled,
            "audio_log_dir": SpeechRecognizer.audio_log_config.output_dir,
            "vad_config": SpeechRecognizer.vad_config.to_dict(),
            "continuous_recognition": cls.continuous_recognition
        }

