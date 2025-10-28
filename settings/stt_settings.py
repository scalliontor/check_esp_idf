from pathlib import Path

# ===== Model Paths =====
ROOT_DIR = Path(__file__).resolve().parent.parent
# Fix case to match actual folder name on disk (Linux is case-sensitive)
MODEL_DIR = ROOT_DIR / "models" / "Zipformer"

# ===== Model Files =====
# Các file này sẽ được tự động tìm kiếm theo pattern
TOKENS_FILE_PATTERNS = ["tokens.txt"]
ENCODER_FILE_PATTERNS = ["encoder-epoch-20-avg-10.onnx", "encoder*.onnx"]
DECODER_FILE_PATTERNS = ["decoder-epoch-20-avg-10.onnx", "decoder*.onnx"]
JOINER_FILE_PATTERNS = ["joiner-epoch-20-avg-10.onnx", "joiner*.onnx"]

# ===== Audio Processing =====
SAMPLE_RATE = 16000  # Hz - ZipFormer yêu cầu 16kHz
FEATURE_DIM = 80     # Mel filterbank dimension

# ===== Recognition Settings =====
NUM_THREADS = 4
DECODING_METHOD = "greedy_search"  # Options: greedy_search, modified_beam_search
PROVIDER = "cpu"  # Options: cpu, cuda, coreml

# ===== Input/Output =====
DEFAULT_INPUT_AUDIO = ROOT_DIR / "data" / "ref1.wav"