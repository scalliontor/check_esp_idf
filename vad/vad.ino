#include <Arduino.h>
#include "driver/i2s.h"
#include <WiFi.h>
#include <ArduinoWebsockets.h>

using namespace websockets;

// ===============================================================
// 1. CẤU HÌNH
// ===============================================================

// --- Cấu hình Mạng & WebSocket ---
const char* ssid = "iPhone của hành";         // <-- THAY ĐỔI TÊN WIFI
const char* password = "123456780"; // <-- THAY ĐỔI MẬT KHẨU WIFI
const char* websocket_server_host = "172.20.10.02"; // <-- THAY ĐỔI IP CỦA SERVER
const uint16_t websocket_server_port = 8000;
const char* websocket_server_path = "/ws";

// --- Chân cắm I2S ---
#define I2S_MIC_SERIAL_CLOCK    18
#define I2S_MIC_WORD_SELECT     17
#define I2S_MIC_SERIAL_DATA     16
#define I2S_SPEAKER_SERIAL_CLOCK 37
#define I2S_SPEAKER_WORD_SELECT  38
#define I2S_SPEAKER_SERIAL_DATA  36

// --- Cài đặt I2S ---
#define I2S_SAMPLE_RATE         16000
#define I2S_BITS_PER_SAMPLE     I2S_BITS_PER_SAMPLE_16BIT
#define I2S_MIC_PORT            I2S_NUM_0
#define I2S_SPEAKER_PORT        I2S_NUM_1

// Kích thước buffer đọc I2S, PHẢI KHỚP VỚI VAD_CHUNK_SIZE CỦA SERVER
#define I2S_READ_CHUNK_SIZE     960 

// --- Cấu hình Âm thanh Loa ---
#define SPEAKER_GAIN            8.0f

// ===============================================================
// 2. BIẾN TOÀN CỤC
// ===============================================================

WebsocketsClient client;

enum State {
  STATE_STREAMING,         // Đọc mic và gửi đi
  STATE_WAITING,           // Đã gửi xong, chờ server xử lý
  STATE_PLAYING_RESPONSE   // Tạm dừng mic, chỉ phát loa
};
volatile State currentState = STATE_STREAMING;

byte i2s_read_buffer[I2S_READ_CHUNK_SIZE];

// ===============================================================
// 3. CÁC HÀM CÀI ĐẶT I2S
// ===============================================================
void setup_i2s_input() {
    Serial.println("Configuring I2S Input (Microphone)...");
    i2s_config_t i2s_mic_config = {.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX), .sample_rate = I2S_SAMPLE_RATE, .bits_per_sample = I2S_BITS_PER_SAMPLE, .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S, .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1, .dma_buf_count = 8, .dma_buf_len = 256};
    i2s_pin_config_t i2s_mic_pins = {.bck_io_num = I2S_MIC_SERIAL_CLOCK, .ws_io_num = I2S_MIC_WORD_SELECT, .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = I2S_MIC_SERIAL_DATA};
    ESP_ERROR_CHECK(i2s_driver_install(I2S_MIC_PORT, &i2s_mic_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_MIC_PORT, &i2s_mic_pins));
}
void setup_i2s_output() {
    Serial.println("Configuring I2S Output (Speaker)...");
    i2s_config_t i2s_speaker_config = {.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX), .sample_rate = I2S_SAMPLE_RATE, .bits_per_sample = I2S_BITS_PER_SAMPLE, .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S, .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1, .dma_buf_count = 8, .dma_buf_len = 256, .tx_desc_auto_clear = true};
    i2s_pin_config_t i2s_speaker_pins = {.bck_io_num = I2S_SPEAKER_SERIAL_CLOCK, .ws_io_num = I2S_SPEAKER_WORD_SELECT, .data_out_num = I2S_SPEAKER_SERIAL_DATA, .data_in_num = I2S_PIN_NO_CHANGE};
    ESP_ERROR_CHECK(i2s_driver_install(I2S_SPEAKER_PORT, &i2s_speaker_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_SPEAKER_PORT, &i2s_speaker_pins));
    ESP_ERROR_CHECK(i2s_zero_dma_buffer(I2S_SPEAKER_PORT));
}


// ===============================================================
// 4. WEBSOCKET & ÂM THANH
// ===============================================================

void onWebsocketEvent(WebsocketsEvent event, String data) {
    if (event == WebsocketsEvent::ConnectionOpened) {
        Serial.println("Websocket connection opened. Starting to stream audio.");
        currentState = STATE_STREAMING; 
    } else if (event == WebsocketsEvent::ConnectionClosed) {
        Serial.println("Websocket connection closed.");
    }
}

void onWebsocketMessage(WebsocketsMessage message) {
    if (message.isText()) {
        String text_msg = String(message.c_str());
        Serial.printf("Server sent text: %s\n", text_msg.c_str());

        if (text_msg == "PROCESSING_START") {
            Serial.println("Server is processing. Pausing microphone.");
            currentState = STATE_WAITING;
        }
        else if (text_msg == "TTS_END") {
            Serial.println("End of TTS. Returning to streaming mode.");
            currentState = STATE_STREAMING;
        }
    }
    else if (message.isBinary()) {
        if (currentState != STATE_PLAYING_RESPONSE) {
            Serial.println("Receiving audio from server, pausing mic and starting playback...");
            currentState = STATE_PLAYING_RESPONSE;
            i2s_zero_dma_buffer(I2S_SPEAKER_PORT);
        }
        
        size_t len = message.length();
        int16_t temp_write_buffer[len / sizeof(int16_t)];
        memcpy(temp_write_buffer, message.c_str(), len);
        
        for (int i = 0; i < len / sizeof(int16_t); i++) {
          float amplified = temp_write_buffer[i] * SPEAKER_GAIN;
          if (amplified > 32767) amplified = 32767; 
          if (amplified < -32768) amplified = -32768;
          temp_write_buffer[i] = (int16_t)amplified;
        }
        
        size_t bytes_written = 0;
        i2s_write(I2S_SPEAKER_PORT, temp_write_buffer, len, &bytes_written, portMAX_DELAY);
    }
}

void audio_processing_task(void *pvParameters) {
  size_t bytes_read;
  while (true) {
    if (currentState == STATE_STREAMING) {
        i2s_read(I2S_MIC_PORT, i2s_read_buffer, I2S_READ_CHUNK_SIZE, &bytes_read, portMAX_DELAY);
        if (bytes_read == I2S_READ_CHUNK_SIZE && client.available()) {
            client.sendBinary((const char*)i2s_read_buffer, bytes_read);
        }
    } else {
        vTaskDelay(pdMS_TO_TICKS(20));
    }
  }
}

// ===============================================================
// 5. SETUP & LOOP
// ===============================================================

void setup() {
  Serial.begin(115200);
  while (!Serial);
  
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  setup_i2s_input();
  setup_i2s_output();

  client.onEvent(onWebsocketEvent);
  client.onMessage(onWebsocketMessage);
  
  Serial.printf("Connecting to WebSocket server: %s:%d%s\n", websocket_server_host, websocket_server_port, websocket_server_path);
  client.connect(websocket_server_host, websocket_server_port, websocket_server_path);

  xTaskCreatePinnedToCore(
      audio_processing_task, "Audio Processing Task",
      4096, NULL, 10, NULL, 1);

  Serial.println("==============================================");
  Serial.println("       Voice Assistant Client Ready");
  Serial.println("==============================================");
}

void loop() {
  client.poll();
  if (!client.available()) {
    Serial.println("WebSocket disconnected. Reconnecting...");
    if (!client.connect(websocket_server_host, websocket_server_port, websocket_server_path)) {
      Serial.println("Reconnect attempt failed.");
      delay(2000);
    } else {
      Serial.println("Reconnected successfully.");
    }
  }
  delay(10);
}