
# セットアップ手順

## 1. 仮想環境作成（推奨）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

## 2. 依存関係インストール
pip install -r requirements.txt

## 3. 初回実行時のモデルダウンロード
# WhisperとSilero VADのモデルが自動ダウンロードされます
# インターネット接続が必要です

## 4. ディレクトリ構造作成
mkdir static
# index.htmlをstatic/index.htmlとして保存
# admin.htmlをstatic/admin.htmlとして保存（管理画面）

## 5. サーバー起動
python main.py

## 6. アクセス
# メインアプリ: http://localhost:8000
# 管理画面: http://localhost:8000/admin

# プロジェクト構造
audio-recognition-app/
├── main.py              # FastAPIサーバー（VAD + Whisper + ログ機能）
├── requirements.txt     # 依存関係
├── static/
│   ├── index.html      # メイン音声認識画面
│   └── admin.html      # 管理画面
├── audio_logs/         # 音声ログファイル（自動作成）
│   ├── *.raw          # RAW音声ファイル
│   └── *.meta         # メタデータファイル
└── README.md

# 新機能: 音声ログ機能

## 音声ログファイル形式

### RAWファイル (.raw)
- 形式: Float32 little-endian
- サンプリングレート: 16kHz
- チャンネル数: 1 (モノラル)
- ファイル名: audio_YYYYMMDD_HHMMSS_mmm_session_ID.raw

### メタデータファイル (.meta)
```json
{
  "filename": "audio_20241201_143022_123_session_12345.raw",
  "session_id": 12345,
  "timestamp": "20241201_143022_123",
  "sample_rate": 16000,
  "channels": 1,
  "data_type": "float32",
  "duration_seconds": 2.5,
  "samples": 40000
}
```

## 管理画面機能

### アクセス方法
http://localhost:8000/admin

### 主な機能
1. **サーバー状態監視**
   - アクティブセッション数
   - モデル読み込み状況
   - 音声ログ機能状態

2. **音声ログ設定**
   - 有効/無効の切り替え
   - 出力ディレクトリの変更
   - 最大ファイル数の設定

3. **ログファイル管理**
   - ファイル一覧表示
   - ファイルサイズと期間の確認
   - 総ファイル数・サイズの表示

## API エンドポイント

### 設定管理
- GET `/config/audio-log` - 現在の音声ログ設定を取得
- POST `/config/audio-log` - 音声ログ設定を更新

### ログファイル管理
- GET `/logs/audio/list` - 音声ログファイル一覧を取得

### システム状態
- GET `/health` - サーバー状態とログ機能状態を取得

## 音声ログ設定例

### 音声ログを無効にする
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### 出力ディレクトリを変更
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"output_dir": "/path/to/custom/logs"}'
```

### 最大ファイル数を変更
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"max_files": 500}'
```

## RAW音声ファイルの再生方法

### FFmpegを使用
```bash
# RAWファイルをWAVに変換
ffmpeg -f f32le -ar 16000 -ac 1 -i audio_file.raw output.wav

# 直接再生
ffplay -f f32le -ar 16000 -ac 1 audio_file.raw
```

### Pythonで読み込み
```python
import numpy as np
import soundfile as sf

# RAWファイルを読み込み
audio_data = np.fromfile('audio_file.raw', dtype=np.float32)

# WAVファイルとして保存
sf.write('output.wav', audio_data, 16000)
```

## パフォーマンス最適化

### 音声ログ無効化（最高パフォーマンス）
- 管理画面または設定APIで音声ログを無効化
- ファイルI/Oが発生しないため最高速度

### ディスク容量管理
- 最大ファイル数を適切に設定
- 古いファイルは自動削除される
- 定期的なクリーンアップが実行される

### ストレージ要件
- 1分間の音声 ≈ 3.84MB (16kHz Float32)
- 1時間の音声 ≈ 230MB
- 1日10時間使用 ≈ 2.3GB

## トラブルシューティング

### 音声ログファイルが作成されない
1. 音声ログが有効になっているか確認
2. 出力ディレクトリの書き込み権限を確認
3. ディスク容量を確認

### ファイルアクセスエラー
- 出力ディレクトリのパーミッションを確認
- 他のプロセスがファイルを使用していないか確認

### 管理画面にアクセスできない
- admin.htmlがstatic/に配置されているか確認
- サーバーが正常に起動しているか確認

## セキュリティ考慮事項

### 本番環境での使用
- 管理画面へのアクセス制限を実装
- 音声ログファイルのアクセス権限を適切に設定
- HTTPS通信の使用を推奨

### プライバシー保護
- 音声ログファイルの適切な管理
- 不要になったファイルの安全な削除
- アクセスログの監視
