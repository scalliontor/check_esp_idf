import os
from pathlib import Path

# ===== API Configuration =====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAVJ-Hr8Qge3sQQq_A5vbNIBg8TEM6AZCg")
GEMINI_MODEL = "gemini-2.5-flash" 

# ===== Thinking/Chain-of-Thought Settings =====
USE_THINKING = True
THINKING_BUDGET = -1  # -1 = dynamic thinking, 0 = disabled, >0 = fixed budget
INCLUDE_THOUGHTS = False  # Set True to see model's reasoning process

# ===== RAG Configuration =====
ROOT_DIR = Path(__file__).resolve().parent.parent
RAG_DIR = ROOT_DIR / "rag_docs"  # Thư mục chứa tài liệu .txt cho RAG
RAG_CHUNK_SIZE = 500  # Kích thước mỗi chunk
RAG_CHUNK_OVERLAP = 50  # Overlap giữa các chunk
RAG_TOP_K = 3  # Số lượng chunk liên quan nhất được lấy ra

# ===== Chat History =====
HISTORY_DIR = ROOT_DIR / "chat_history"
MAX_HISTORY_TURNS = 8  # Số lượt hội thoại tối đa được lưu

# ===== System Prompt =====
ROLE_PROMPT = (
    "Bạn là một đứa trẻ lớp 1 đang nói chuyện với một bạn cũng học lớp 1. Bạn xưng Tớ, gọi Cậu\\n"
    "Nhiệm vụ của bạn là cùng học tập với bạn ấy, giải thích chậm rãi, dễ hiểu,\\n"
    "dùng từ ngữ ngây thơ, hồn nhiên, lễ phép.\\n"
    "Luôn khuyến khích bạn ấy đặt câu hỏi.\\n"
    "Tránh dùng từ ngữ người lớn, tránh giáo điều.\\n"
)

SAFETY_PROMPT = (
    "Không tiết lộ suy luận nội bộ; chỉ trả lời kết luận ngắn gọn, rõ ràng.\\n"
    "Nếu câu hỏi không phù hợp lứa tuổi lớp 1, lịch sự từ chối."
)

# ===== Generation Settings =====
TEMPERATURE = 0.7
MAX_OUTPUT_TOKENS = 1024
TOP_P = 0.95
TOP_K = 40