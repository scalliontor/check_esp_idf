from pathlib import Path
from typing import Optional
import time

from .stt import STTEngine
from .tts import TTSEngine
from .llm import LLMEngine


class VoiceAssistantPipeline:
    """
    Complete Voice Assistant Pipeline
    Flow: Audio Input -> STT -> LLM -> TTS -> Audio Output
    """
    
    def __init__(self):
        print("\\n" + "="*60)
        print("🚀 Initializing Voice Assistant Pipeline")
        print("="*60 + "\\n")
        
        self.stt_engine = STTEngine()
        self.llm_engine = LLMEngine()
        self.tts_engine = TTSEngine()
        
        print("\\n" + "="*60)
        print("✅ Pipeline Ready!")
        print("="*60 + "\\n")
    
    def process(
        self,
        audio_input_path: str,
        audio_output_path: Optional[str] = None,
        session_id: str = "default"
    ) -> dict:
        """
        Xử lý pipeline hoàn chỉnh
        
        Args:
            audio_input_path: Đường dẫn file audio input
            audio_output_path: Đường dẫn file audio output (optional)
            session_id: Session ID cho conversation tracking
            
        Returns:
            dict: {
                "input_text": str,
                "response_text": str,
                "output_audio": Path,
                "processing_time": float
            }
        """
        start_time = time.time()
        
        print("\\n" + "🔄 " + "="*58)
        print("STARTING PIPELINE PROCESSING")
        print("="*60 + "\\n")
        
        # Step 1: STT
        print("📍 STEP 1: Speech to Text")
        print("-" * 60)
        input_text = self.stt_engine.transcribe(audio_input_path)
        print(f"✓ Transcribed: {input_text}\\n")
        
        # Step 2: LLM
        print("📍 STEP 2: Language Model Processing")
        print("-" * 60)
        response_text = self.llm_engine.chat(input_text, session_id=session_id)
        print(f"✓ Generated response\\n")
        
        # Step 3: TTS
        print("📍 STEP 3: Text to Speech")
        print("-" * 60)
        output_audio = self.tts_engine.synthesize(
            response_text,
            output_path=audio_output_path
        )
        print(f"✓ Audio generated: {output_audio}\\n")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        print("="*60)
        print(f"✅ PIPELINE COMPLETED in {processing_time:.2f}s")
        print("="*60 + "\\n")
        
        return {
            "input_text": input_text,
            "response_text": response_text,
            "output_audio": output_audio,
            "processing_time": processing_time
        }
    
    def text_to_speech_only(self, text: str, output_path: Optional[str] = None) -> Path:
        """Chỉ chạy TTS"""
        return self.tts_engine.synthesize(text, output_path)
    
    def speech_to_text_only(self, audio_path: str) -> str:
        """Chỉ chạy STT"""
        return self.stt_engine.transcribe(audio_path)
    
    def chat_only(self, text: str, session_id: str = "default") -> str:
        """Chỉ chạy LLM"""
        return self.llm_engine.chat(text, session_id=session_id)


if __name__ == "__main__":
    import sys
    
    # Example usage
    pipeline = VoiceAssistantPipeline()
    
    # Nếu có argument là file audio
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        result = pipeline.process(audio_file)
        
        print("\\n" + "="*60)
        print("RESULT SUMMARY")
        print("="*60)
        print(f"Input Text:     {result['input_text']}")
        print(f"Response Text:  {result['response_text']}")
        print(f"Output Audio:   {result['output_audio']}")
        print(f"Processing Time: {result['processing_time']:.2f}s")
        print("="*60 + "\\n")
    else:
        print("Usage: python pipeline.py <audio_input_file>")
        print("\\nTesting individual components instead...\\n")
