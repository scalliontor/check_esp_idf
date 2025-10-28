"""
Text-to-Speech Module with Debug Logging
Model: ZipVoice
"""
import sys
import subprocess
from pathlib import Path
from settings import tts_settings as cfg

class TTSEngine:
    def __init__(self):
        self._validate_setup()
        print(f"DEBUG: Ensuring output dir {cfg.OUTPUT_AUDIO_DIR}")
        cfg.OUTPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    def _validate_setup(self):
        print("🔧 Validating TTS setup...")
        if not cfg.ZIPVOICE_CODE_DIR.exists():
            raise FileNotFoundError(f"Code dir not found: {cfg.ZIPVOICE_CODE_DIR}")
        if not cfg.MODEL_DIR.exists():
            raise FileNotFoundError(f"Model dir not found: {cfg.MODEL_DIR}")
        print("✅ TTS setup validated")

    def _find_checkpoint(self):
        for ext in cfg.CHECKPOINT_EXTENSIONS:
            files = list(cfg.MODEL_DIR.glob(f"*{ext}"))
            if files:
                print(f"DEBUG: Found checkpoint {files[0].name}")
                return files[0].name
        print("DEBUG: No checkpoint found")
        return None

    def synthesize(self, text, output_path=None, ref_audio=None, prompt_text=None):
        print(f"🔊 Synthesizing: {text[:30]}...")
        checkpoint = self._find_checkpoint()
        if not checkpoint:
            raise FileNotFoundError(f"Checkpoint missing in {cfg.MODEL_DIR}")

        ref_audio = ref_audio or cfg.DEFAULT_REF_AUDIO
        prompt_text = prompt_text or cfg.DEFAULT_PROMPT_TEXT
        output_path = Path(output_path) if output_path else cfg.OUTPUT_AUDIO_DIR / "output.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "zipvoice.bin.infer_zipvoice",
            "--model-name", cfg.MODEL_NAME,
            "--model-dir", str(cfg.MODEL_DIR),
            "--checkpoint-name", checkpoint,
            "--prompt-wav", str(ref_audio),
            "--prompt-text", prompt_text,
            "--text", text,
            "--res-wav-path", str(output_path),
            "--num-step", str(cfg.NUM_STEP),
            "--remove-long-sil", str(cfg.REMOVE_LONG_SIL),
            "--tokenizer", cfg.TOKENIZER,
            "--lang", cfg.LANG,
        ]

        print("DEBUG: Command:", cmd)
        result = subprocess.run(cmd, cwd=str(cfg.ZIPVOICE_CODE_DIR), capture_output=True, text=True)
        print("DEBUG: returncode", result.returncode)
        print("DEBUG: stdout", result.stdout)
        print("DEBUG: stderr", result.stderr)

        if result.returncode != 0:
            raise RuntimeError(f"TTS failed, code {result.returncode}")
        if not output_path.exists():
            raise RuntimeError(f"Output missing: {output_path}")

        print(f"✅ Audio generated: {output_path}")
        return output_path

if __name__ == '__main__':
    print("\n=== TTS Debug Run ===")
    engine = TTSEngine()
    path = engine.synthesize("Xin chao cac ban!", output_path="audio_cache/test.wav")
    print(f"Result at {path}")
