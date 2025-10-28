"""
Speech-to-Text Module with Debug Logging
Model: ZipFormer with sherpa_onnx
"""
import numpy as np
import soundfile as sf
import sherpa_onnx
from pathlib import Path
from settings import stt_settings as cfg

class STTEngine:
    def __init__(self):
        self.recognizer = None
        self._initialize_model()

    def _find_model_file(self, patterns):
        for pattern in patterns:
            if '*' in pattern:
                files = list(cfg.MODEL_DIR.glob(pattern))
                if files:
                    print(f"DEBUG: Found model file {files[0]}")
                    return str(files[0])
            else:
                file_path = cfg.MODEL_DIR / pattern
                if file_path.exists():
                    print(f"DEBUG: Found model file {file_path}")
                    return str(file_path)
        raise FileNotFoundError(f"Model file not found for patterns: {patterns}")

    def _initialize_model(self):
        print("🔧 Initializing STT model...")
        print(f"DEBUG: MODEL_DIR = {cfg.MODEL_DIR}")
        tokens = self._find_model_file(cfg.TOKENS_FILE_PATTERNS)
        encoder = self._find_model_file(cfg.ENCODER_FILE_PATTERNS)
        decoder = self._find_model_file(cfg.DECODER_FILE_PATTERNS)
        joiner = self._find_model_file(cfg.JOINER_FILE_PATTERNS)

        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=tokens,
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            num_threads=cfg.NUM_THREADS,
            sample_rate=cfg.SAMPLE_RATE,
            feature_dim=cfg.FEATURE_DIM,
            decoding_method=cfg.DECODING_METHOD,
            provider=cfg.PROVIDER,
        )
        print("✅ STT model initialized successfully")

    def transcribe_from_file(self, audio_path):
        path = Path(audio_path)
        print(f"DEBUG: Checking audio path {path}")
        print("DEBUG: Exists?", path.exists())
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        try:
            wav, sr = sf.read(str(path), dtype='float32')
            print(f"DEBUG: Loaded audio, shape={wav.shape}, sr={sr}")
        except Exception as e:
            print("ERROR reading audio:", e)
            raise

        if wav.ndim > 1:
            wav = wav[:, 0]
        if sr != cfg.SAMPLE_RATE:
            print(f"DEBUG: Resampling from {sr} to {cfg.SAMPLE_RATE}")
            new_len = int(len(wav) * cfg.SAMPLE_RATE / sr)
            wav = np.interp(
                np.linspace(0,1,new_len),
                np.linspace(0,1,len(wav)),
                wav
            ).astype('float32')
            sr = cfg.SAMPLE_RATE

        stream = self.recognizer.create_stream()
        stream.accept_waveform(sr, wav)
        self.recognizer.decode_stream(stream)

        res = stream.result
        print(f"DEBUG: Recognition result: {res}")
        return res.text

    def transcribe(self, audio_input_path):
        """Alias kept for compatibility with pipeline.py"""
        return self.transcribe_from_file(audio_input_path)

if __name__ == '__main__':
    print("\n=== STT Debug Run ===")
    engine = STTEngine()
    text = engine.transcribe_from_file(cfg.DEFAULT_INPUT_AUDIO)
    print(f"\nFinal transcription: {text}")
