import asyncio
import wave
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os
import torch
from collections import deque
import numpy as np

# --- IMPORT PIPELINE TỪ THƯ MỤC MODULES ---
from modules.pipeline import VoiceAssistantPipeline

# --- Cấu hình ---
SAMPLE_RATE = 16000
BIT_DEPTH_BYTES = 2
CHANNELS = 1
AUDIO_CHUNK_SIZE = 1024 # Kích thước chunk để gửi lại cho client

# --- Cấu hình VAD ---
# SỬA LỖI: Model yêu cầu chính xác 512 mẫu 16-bit (1024 bytes)
VAD_CHUNK_SIZE = 1024

VAD_SPEECH_THRESHOLD = 0.5
VAD_SILENCE_FRAMES_TRIGGER = 1
VAD_SILENCE_FRAMES_END = 25
VAD_BUFFER_FRAMES = 5 # Kích thước của bộ đệm trước

app = FastAPI()

print("\n... (các dòng print khởi tạo pipeline) ...\n")
pipeline = VoiceAssistantPipeline()
print("\n... (các dòng print pipeline ready) ...\n")

try:
    torch.set_num_threads(1)
    vad_model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False
    )
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    print("Silero VAD model loaded successfully.")
except Exception as e:
    print(f"Error loading Silero VAD model: {e}")
    vad_model = None

def save_audio_to_wav(audio_data: bytes, folder: str = "audio_files") -> str:
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    filename = os.path.join(folder, f"recording_{timestamp}.wav")
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(BIT_DEPTH_BYTES)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        print(f"\nAudio received and saved to: {filename}")
        return filename
    except Exception as e:
        print(f"\nError saving WAV file: {e}")
        return ""

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"Client connected from: {websocket.client.host}")
    if vad_model is None:
        await websocket.close(code=1011, reason="VAD model not loaded")
        return
    
    is_speaking = False
    silence_counter = 0
    speech_trigger_counter = 0
    is_processing = False
    
    # <<< PHẦN 1: Khởi tạo bộ đệm trước
    pre_buffer = deque(maxlen=VAD_BUFFER_FRAMES) 
    speech_buffer = []

    try:
        while True:
            data = await websocket.receive_bytes()

            if is_processing:
                continue

            if len(data) != VAD_CHUNK_SIZE:
                print(f"\nWarning: Received chunk of size {len(data)}, expected {VAD_CHUNK_SIZE}. Ignoring.")
                continue

            audio_numpy = np.frombuffer(data, dtype=np.int16)
            audio_tensor = torch.from_numpy(audio_numpy).float() / 32768.0
            
            with torch.no_grad():
                speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()

            bar_length = 50
            filled_len = int(bar_length * speech_prob)
            bar = '█' * filled_len + '-' * (bar_length - filled_len)
            print(f'\rVAD |{bar}| Prob: {speech_prob:.2f}', end="")

            if speech_prob > VAD_SPEECH_THRESHOLD:
                silence_counter = 0
                if not is_speaking:
                    speech_trigger_counter += 1
                    if speech_trigger_counter >= VAD_SILENCE_FRAMES_TRIGGER:
                        print("\n==> Voice activity detected. Start recording.")
                        is_speaking = True
                        # <<< PHẦN 3: Đổ bộ đệm trước vào bộ đệm chính
                        speech_buffer.extend(list(pre_buffer))
                if is_speaking:
                    speech_buffer.append(data)
            else:
                speech_trigger_counter = 0
                if is_speaking:
                    silence_counter += 1
                    speech_buffer.append(data)
                    if silence_counter >= VAD_SILENCE_FRAMES_END:
                        print("\n==> Silence detected. End of utterance.")
                        is_processing = True
                        await websocket.send_text("PROCESSING_START")
                        full_audio_data = b"".join(speech_buffer)
                        input_audio_path = save_audio_to_wav(full_audio_data)
                        if input_audio_path:
                            try:
                                result = await asyncio.to_thread(pipeline.process, audio_input_path=input_audio_path)
                                output_audio_path = result.get("output_audio") if isinstance(result, dict) else None
                                if output_audio_path and os.path.exists(output_audio_path):
                                    try:
                                        with wave.open(output_audio_path, 'rb') as wf_out:
                                            # ... (code streaming âm thanh về client) ...
                                            frames_per_chunk = max(1, AUDIO_CHUNK_SIZE // BIT_DEPTH_BYTES)
                                            while True:
                                                frames = wf_out.readframes(frames_per_chunk)
                                                if not frames:
                                                    break
                                                await websocket.send_bytes(frames)
                                    except Exception as e:
                                        print(f"\nFailed to stream WAV frames: {e}")
                                else:
                                    print("\nPipeline did not return a valid audio output path.")
                            except Exception as e:
                                print(f"\nAn error occurred during pipeline processing: {e}")
                            finally:
                                await websocket.send_text("TTS_END")
                                print("\nFinished streaming response.")
                        is_speaking = False
                        silence_counter = 0
                        speech_buffer.clear()
                        pre_buffer.clear()
                        is_processing = False
                else:
                    # <<< PHẦN 2: Thêm dữ liệu vào bộ đệm trước khi im lặng
                    pre_buffer.append(data)

    except WebSocketDisconnect:
        print(f"\nClient {websocket.client.host} disconnected.")
    except Exception as e:
        import traceback
        print(f"\nA critical error occurred in websocket connection:")
        traceback.print_exc()

@app.get("/")
def read_root():
    return {"status": "Voice Assistant Server is running"}