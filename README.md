## Quickstart: ESP32-S3 VAD + FastAPI server

Minimal steps to run the ESP32-S3 (vad.ino) with the VAD server (vad_server.py).

### 1) Server setup (once)

```bash
cd test_wake_net
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt fastapi uvicorn

# Put models here (required):
#   models/ZipFormer/{tokens.txt, encoder*.onnx, decoder*.onnx, joiner*.onnx}
#   models/ZipVoice/{zipvoice.pt, tokens.txt, model.json}
```

### 2) Run the VAD server

```bash
cd test_wake_net    # if not already there
uvicorn vad_server:app --host 0.0.0.0 --port 8000
# Visit http://<server-ip>:8000/ for a simple status
```

### 3) Configure ESP32 firmware

Edit `vad/vad.ino`:
- Set `ssid` and `password` to your Wi‑Fi
- Set `websocket_server_host` to your server IP (avoid leading zeros, e.g., 172.20.10.2)
- Leave `websocket_server_port = 8000` and `websocket_server_path = "/ws"`

Important – find the correct server IP:

```bash
# On the Linux server
hostname -I      # quick list of local IPs
ip addr show     # detailed view; look for the Wi‑Fi interface (e.g., wlan0)
```

- Use the IP on the same Wi‑Fi network as the ESP32.
- On iPhone hotspot, the phone is usually 172.20.10.1 and your Linux machine gets 172.20.10.2.
- Do NOT use leading zeros in any octet (e.g., use 172.20.10.2, not 172.20.10.02).

Snippet in `vad/vad.ino` to edit:

```cpp
const char* ssid = "<YOUR_WIFI_NAME>";
const char* password = "<YOUR_WIFI_PASSWORD>";
const char* websocket_server_host = "<SERVER_IP_HERE>"; // e.g., "172.20.10.2"
const uint16_t websocket_server_port = 8000;
const char* websocket_server_path = "/ws";
```

### 4) Build, upload, and monitor (Arduino CLI)

```bash
# List boards/ports
arduino-cli board list

# Compile the sketch
arduino-cli compile --fqbn esp32:esp32:esp32s3 ./vad

# Upload (adjust port if needed)
arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:esp32s3 ./vad

# Monitor serial
arduino-cli monitor -p /dev/ttyACM0 --fqbn esp32:esp32:esp32s3 -c baudrate=115200
```

### 5) Use it

- Speak near the mic. The ESP32 streams 960‑byte PCM frames when it hears speech.
- Server responds: `PROCESSING_START` → binary PCM audio → `TTS_END`.
- The ESP32 plays the audio, then resumes listening.

Tips:
- If STT model isn’t found: ensure folder name `models/ZipFormer` (capital F) and required files exist.
- If audio sounds wrong: make sure TTS outputs 16 kHz, mono, 16‑bit (server logs a warning if not).

