from pathlib import Path

# ===== Model Paths =====
ROOT_DIR = Path(__file__).resolve().parent.parent
ZIPVOICE_CODE_DIR = ROOT_DIR / "ZipVoice"
MODEL_DIR = ROOT_DIR / "models" / "ZipVoice"

# ===== Audio Files =====
REF_AUDIO_DIR = ROOT_DIR / "data"
DEFAULT_REF_AUDIO = REF_AUDIO_DIR / "ref1.wav"
OUTPUT_AUDIO_DIR = ROOT_DIR / "audio_cache"

# ===== Reference Audio Prompt =====
# Text tương ứng với audio tham chiếu
DEFAULT_PROMPT_TEXT = (
    "Hôm nay tôi bước lên sân khấu với niềm tự tin mới, "
    "và tiếng vỗ tay của khán giả khiến trái tim tôi tràn đầy cảm xúc và hy vọng."
)

# ===== Model Settings =====
MODEL_NAME = "zipvoice"
NUM_STEP = 10 
REMOVE_LONG_SIL = True  # Loại bỏ khoảng lặng dài
TOKENIZER = "espeak"
LANG = "vi"  # Vietnamese

# ===== Checkpoint Settings =====
CHECKPOINT_EXTENSIONS = ['.pt', '.safetensors']