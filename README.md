# Browser Speech Recognition System

This project is an open-source system that enables real-time speech recognition in web browsers.
It consists of server and client components using the Whisper speech recognition engine and Silero VAD (Voice Activity Detection).

## Setup Instructions

### 1. Create Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. First-time Model Download
Whisper and Silero VAD models will be automatically downloaded (internet connection required)

### 4. Start Server
```bash
python main.py
```

### 5. Access
- Main app: http://localhost:8000
- Admin panel: http://localhost:8000/admin

## Project Structure
```
speech-recognition-test/
├── main.py                    # FastAPI server (VAD + Whisper + audio logging)
├── requirements.txt           # Python dependencies
├── config/                    # Configuration files
│   ├── app-config.env        # Application settings
│   ├── audio-log-config.json # Audio logging configuration
│   └── vad-config.json       # VAD settings
├── src/                       # Python source code
│   ├── http_speech_recognition_service.py    # Main speech recognition service
│   ├── http_speech_recognition_admin_service.py # Admin functionality service
│   └── speech_recognition/    # Speech recognition modules
│       ├── audio_logger.py        # Audio logging functionality
│       ├── speech_recognizer.py   # Whisper speech recognition
│       ├── whisper_processor.py   # Whisper processing
│       ├── numpy_ring_buffer.py   # Ring buffer
│       ├── audio_log_config.py    # Audio logging configuration
│       └── vad_config.py          # VAD configuration
├── public/                    # Web client
│   ├── index.html            # Main speech recognition interface
│   ├── admin.html            # Admin panel
│   ├── css/                  # Stylesheets
│   └── js/                   # JavaScript
│       ├── speech_recognition/    # Speech recognition related JS
│       └── ui-elements/          # UI elements
└── audio_logs/               # Audio log files (auto-created)
    ├── *.raw                # Raw audio data
    └── *.meta               # Metadata files
```

# New Feature: Audio Logging

## Audio Log File Format

### RAW Files (.raw)
- Format: Float32 little-endian
- Sample Rate: 16kHz
- Channels: 1 (mono)
- Filename: audio_YYYYMMDD_HHMMSS_mmm_session_ID.raw

### Metadata Files (.meta)
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

## Admin Panel Features

### Access Method
http://localhost:8000/admin

### Main Features
1. **Server Status Monitoring**
   - Active session count
   - Model loading status
   - Audio logging feature status

2. **Audio Log Configuration**
   - Enable/disable toggle
   - Output directory modification
   - Maximum file count setting

3. **Log File Management**
   - File list display
   - File size and duration verification
   - Total file count and size display

## API Endpoints

### Configuration Management
- GET `/config/audio-log` - Get current audio log settings
- POST `/config/audio-log` - Update audio log settings

### Log File Management
- GET `/logs/audio/list` - Get audio log file list

### System Status
- GET `/health` - Get server status and logging feature status

## Audio Log Configuration Examples

### Disable Audio Logging
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Change Output Directory
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"output_dir": "/path/to/custom/logs"}'
```

### Change Maximum File Count
```bash
curl -X POST http://localhost:8000/config/audio-log \
  -H "Content-Type: application/json" \
  -d '{"max_files": 500}'
```

## Playing RAW Audio Files

### Using FFmpeg
```bash
# Convert RAW file to WAV
ffmpeg -f f32le -ar 16000 -ac 1 -i audio_file.raw output.wav

# Direct playback
ffplay -f f32le -ar 16000 -ac 1 audio_file.raw
```

### Loading with Python
```python
import numpy as np
import soundfile as sf

# Load RAW file
audio_data = np.fromfile('audio_file.raw', dtype=np.float32)

# Save as WAV file
sf.write('output.wav', audio_data, 16000)
```

## Performance Optimization

### Disable Audio Logging (Maximum Performance)
- Disable audio logging via admin panel or configuration API
- Achieves maximum speed as no file I/O occurs

### Disk Space Management
- Set appropriate maximum file count
- Old files are automatically deleted
- Periodic cleanup is performed

### Storage Requirements
- 1 minute of audio ≈ 3.84MB (16kHz Float32)
- 1 hour of audio ≈ 230MB
- 10 hours daily usage ≈ 2.3GB

## Troubleshooting

### Audio Log Files Not Created
1. Verify audio logging is enabled
2. Check write permissions for output directory
3. Verify disk space availability

### File Access Errors
- Check output directory permissions
- Ensure no other processes are using the files

### Cannot Access Admin Panel
- Verify admin.html is placed in static/ directory
- Confirm server is running properly

## Security Considerations

### Production Environment Usage
- Implement access restrictions for admin panel
- Set appropriate permissions for audio log files
- Recommend using HTTPS communication

### Privacy Protection
- Proper management of audio log files
- Safe deletion of unnecessary files
- Monitor access logs