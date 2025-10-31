import asyncio
import wave
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os
import torch
from collections import deque
import numpy as np
from pathlib import Path # Import Path để kiểm tra kiểu dữ liệu
import soundfile as sf

# --- IMPORT PIPELINE TỪ THƯ MỤC MODULES ---
from modules.pipeline import VoiceAssistantPipeline

# --- Cấu hình ---
SAMPLE_RATE = 16000
BIT_DEPTH_BYTES = 2
CHANNELS = 1
# --- Cấu hình VAD ---
VAD_CHUNK_SIZE = 1024
VAD_SPEECH_THRESHOLD = 0.5
VAD_SILENCE_FRAMES_TRIGGER = 1
VAD_SILENCE_FRAMES_END = 50
VAD_BUFFER_FRAMES = 5

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
    connection_closed = False
    
    pre_buffer = deque(maxlen=VAD_BUFFER_FRAMES) 
    speech_buffer = []

    try:
        while True:
            try:
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                print(f"\nClient {websocket.client.host} disconnected during receive.")
                return
            except RuntimeError as e:
                # e.g., "WebSocket is not connected. Need to call accept first." after client closes
                print(f"\nWebSocket runtime error during receive: {e}")
                return

            if is_processing:
                continue

            if len(data) != VAD_CHUNK_SIZE:
                print(f"\nWarning: Received chunk of size {len(data)}, expected {VAD_CHUNK_SIZE}. Ignoring.")
                continue

            # copy() để tránh cảnh báo NumPy non-writable khi chuyển sang torch tensor
            audio_numpy = np.frombuffer(data, dtype=np.int16).copy()
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
                                    # Robust streaming: decode WAV, convert to 16k mono int16 PCM, and stream in paced chunks
                                    try:
                                        # Đọc WAV bằng soundfile để xử lý chuẩn
                                        wav, sr = sf.read(str(output_audio_path), dtype='float32', always_2d=True)
                                        # Chọn kênh mono (trung bình 2 kênh nếu stereo)
                                        if wav.shape[1] > 1:
                                            wav = wav.mean(axis=1)
                                        else:
                                            wav = wav[:, 0]

                                        target_sr = SAMPLE_RATE  # 16k để khớp ESP32
                                        if sr != target_sr:
                                            # Nội suy tuyến tính đơn giản để giảm phụ thuộc
                                            new_len = int(len(wav) * target_sr / sr)
                                            wav = np.interp(
                                                np.linspace(0.0, 1.0, new_len, endpoint=False),
                                                np.linspace(0.0, 1.0, len(wav), endpoint=False),
                                                wav
                                            ).astype('float32')
                                            sr = target_sr

                                        # Chuyển sang int16 PCM
                                        wav = np.clip(wav, -1.0, 1.0)
                                        pcm_int16 = (wav * 32767.0).astype(np.int16)
                                        pcm_bytes = pcm_int16.tobytes()

                                        # Stream theo từng chunk bytes
                                        bytes_per_sample = 2  # int16
                                        # Giữ chunk nhỏ để tránh tràn buffer client (ESP32)
                                        samples_per_chunk = 512  # 512 samples = 1024 bytes ~ 32ms @16kHz
                                        chunk_size_to_send = samples_per_chunk * bytes_per_sample
                                        chunk_duration_sec = samples_per_chunk / float(target_sr)

                                        # Tùy chọn: báo hiệu bắt đầu TTS
                                        # await websocket.send_text("TTS_START")
                                        client_alive = True
                                        for i in range(0, len(pcm_bytes), chunk_size_to_send):
                                            chunk = pcm_bytes[i:i+chunk_size_to_send]
                                            if not chunk or not client_alive:
                                                break
                                            try:
                                                await websocket.send_bytes(chunk)
                                            except Exception as e:
                                                # Client đã đóng kết nối (ví dụ: reset hoặc reconnect)
                                                print("\nClient disconnected during streaming; aborting send loop.")
                                                client_alive = False
                                                connection_closed = True
                                                break
                                            # Pace streaming để gần real-time, giúp client xử lý kịp
                                            await asyncio.sleep(chunk_duration_sec)

                                    except Exception as e:
                                        import traceback
                                        print("\nFailed to stream WAV frames:")
                                        traceback.print_exc()
                                        
                                else:
                                    print("\nPipeline did not return a valid audio output path.")
                            except Exception as e:
                                print(f"\nAn error occurred during pipeline processing: {e}")
                            finally:
                                # Chỉ gửi TTS_END nếu kết nối còn mở
                                try:
                                    await websocket.send_text("TTS_END")
                                    print("\nFinished streaming response.")
                                except Exception:
                                    print("\nClient disconnected before TTS_END could be sent.")
                                # Nếu client đã đóng kết nối, kết thúc handler sớm
                                if connection_closed:
                                    return
                        is_speaking = False
                        silence_counter = 0
                        speech_buffer.clear()
                        pre_buffer.clear()
                        is_processing = False
                else:
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