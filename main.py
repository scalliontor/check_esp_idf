import asyncio
import wave
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os

# --- IMPORT PIPELINE TỪ THƯ MỤC MODULES ---
# Đảm bảo thư mục 'modules' có file __init__.py (dù là file trống)
# để Python nhận diện nó là một package.
from modules.pipeline import VoiceAssistantPipeline

# --- Cấu hình ---
# Các thông số audio này PHẢI KHỚP với code ESP32
SAMPLE_RATE = 16000
BIT_DEPTH_BYTES = 2  # 16-bit = 2 bytes
CHANNELS = 1
AUDIO_TIMEOUT = 0.7  # Tăng nhẹ thời gian chờ để linh hoạt hơn
AUDIO_CHUNK_SIZE = 1024 # Kích thước mỗi đoạn audio gửi về client

# --- Khởi tạo ứng dụng và Pipeline ---
app = FastAPI()

# Khởi tạo pipeline MỘT LẦN DUY NHẤT khi server bắt đầu.
# Việc này giúp tải các mô hình AI lên trước, tránh độ trễ khi xử lý.
pipeline = VoiceAssistantPipeline()

def save_audio_to_wav(audio_data: bytes, folder: str = "audio_files") -> str:
    """Lưu dữ liệu âm thanh thô vào một file WAV."""
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(folder, f"recording_{timestamp}.wav")
    
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(BIT_DEPTH_BYTES)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        print(f"Audio received and saved to: {filename}")
        return filename
    except Exception as e:
        print(f"Error saving WAV file: {e}")
        return ""

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint nhận stream audio, gọi AI pipeline, và stream audio trả về.
    """
    await websocket.accept()
    print(f"Client connected from: {websocket.client.host}")
    
    try:
        # Vòng lặp chính, cho phép xử lý nhiều câu nói trong một kết nối
        while True:
            audio_chunks = []
            
            # 1. NHẬN AUDIO TỪ ESP32
            print("\nListening for audio from client...")
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_bytes(), 
                        timeout=AUDIO_TIMEOUT
                    )
                    audio_chunks.append(data)
                except asyncio.TimeoutError:
                    # Hết thời gian chờ -> người dùng đã ngừng nói
                    break
            
            if not audio_chunks:
                continue # Nếu không có audio, quay lại vòng lặp chờ

            # 2. LƯU FILE AUDIO NHẬN ĐƯỢC
            full_audio_data = b"".join(audio_chunks)
            input_audio_path = save_audio_to_wav(full_audio_data)
            
            if not input_audio_path:
                print("Failed to save input audio. Awaiting next message.")
                continue

            # 3. GỌI AI PIPELINE ĐỂ XỬ LÝ
            try:
                # Gọi hàm process từ pipeline của bạn
                result = pipeline.process(audio_input_path=input_audio_path)
                output_audio_path = result.get("output_audio")

                if not output_audio_path or not os.path.exists(output_audio_path):
                    print("Pipeline did not return a valid audio output path.")
                    continue

                # 4. GỬI AUDIO KẾT QUẢ TRỞ LẠI ESP32
                print(f"Streaming response audio from: {output_audio_path}")
                with open(output_audio_path, 'rb') as audio_file:
                    while True:
                        chunk = audio_file.read(AUDIO_CHUNK_SIZE)
                        if not chunk:
                            break # Đã đọc hết file
                        await websocket.send_bytes(chunk)
                
                print("Finished streaming response.")
                
                # 5. GỬI TÍN HIỆU KẾT THÚC
                # Tín hiệu này rất quan trọng để ESP32 biết và chuyển về trạng thái lắng nghe
                await websocket.send_text("TTS_END")

            except Exception as e:
                print(f"An error occurred during pipeline processing: {e}")

    except WebSocketDisconnect:
        print(f"Client {websocket.client.host} disconnected.")
    except Exception as e:
        print(f"A critical error occurred in websocket connection: {e}")

@app.get("/")
def read_root():
    return {"status": "Voice Assistant Server is running"}