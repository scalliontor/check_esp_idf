import os
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from google import genai
from google.genai import types

from settings import llm_settings as cfg


class SimpleRAG:
    """Simple RAG implementation with chunking and keyword-based search"""
    
    def __init__(
        self,
        folder: str,
        chunk_size: int = None,
        overlap: int = None
    ):
        self.folder = Path(folder)
        self.chunk_size = chunk_size or cfg.RAG_CHUNK_SIZE
        self.overlap = overlap or cfg.RAG_CHUNK_OVERLAP
        self.chunks: List[Tuple[str, str]] = []
        self._loaded = False
    
    def _tokenize(self, s: str) -> List[str]:
        """Tokenize text thành các từ"""
        return re.findall(r"\\w+", s.lower(), flags=re.UNICODE)
    
    def _load(self):
        """Load và chunk các document"""
        if self._loaded:
            return
        
        if not self.folder.exists():
            print(f"⚠️  RAG folder không tồn tại: {self.folder}")
            self.folder.mkdir(parents=True, exist_ok=True)
            self._loaded = True
            return
        
        print(f"📚 Loading RAG documents from {self.folder}...")
        doc_count = 0
        
        for file_path in self.folder.rglob("*.txt"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                
                i = 0
                while i < len(text):
                    chunk = text[i:i + self.chunk_size]
                    self.chunks.append((str(file_path), chunk))
                    i += self.chunk_size - self.overlap
                
                doc_count += 1
            except Exception as e:
                print(f"  ⚠️  Error loading {file_path}: {e}")
        
        print(f"  ✓ Loaded {doc_count} documents, {len(self.chunks)} chunks")
        self._loaded = True
    
    def search(self, query: str, top_k: int = None) -> List[Dict[str, any]]:
        """Tìm kiếm các chunk liên quan nhất"""
        self._load()
        
        if not self.chunks:
            return []
        
        top_k = top_k or cfg.RAG_TOP_K
        q_tokens = set(self._tokenize(query))
        
        scored = []
        for src, chunk in self.chunks:
            c_tokens = set(self._tokenize(chunk))
            score = len(q_tokens & c_tokens)
            if score > 0:
                scored.append((score, src, chunk))
        
        scored.sort(key=lambda x: x, reverse=True)
        
        results = []
        for score, src, chunk in scored[:top_k]:
            results.append({
                "source": Path(src).name,
                "score": int(score),
                "text": chunk
            })
        
        return results


class ChatHistory:
    """Quản lý lịch sử hội thoại"""
    
    def __init__(self, history_dir: str = None):
        self.history_dir = Path(history_dir or cfg.HISTORY_DIR)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "history.jsonl"
        self.memory: Dict[str, List[Dict]] = {}
    
    def add(self, session_id: str, role: str, text: str):
        """Thêm message vào history"""
        messages = self.memory.setdefault(session_id, [])
        messages.append({
            "role": role,
            "content": text,
            "timestamp": time.time()
        })
        
        if len(messages) > cfg.MAX_HISTORY_TURNS * 2:
            self.memory[session_id] = messages[-cfg.MAX_HISTORY_TURNS * 2:]
        
        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "session_id": session_id,
                    "role": role,
                    "content": text,
                    "timestamp": time.time()
                }, ensure_ascii=False) + "\\n")
        except Exception as e:
            print(f"⚠️  Failed to save history: {e}")
    
    def get_history(self, session_id: str) -> List[Dict]:
        """Lấy lịch sử hội thoại"""
        return self.memory.get(session_id, [])
    
    def clear(self, session_id: str):
        """Xóa lịch sử một session"""
        if session_id in self.memory:
            del self.memory[session_id]


class LLMEngine:
    """LLM Engine with Gemini API - Features: Chain of Thought, RAG"""
    
    def __init__(self):
        self.client = None
        self.rag = SimpleRAG(cfg.RAG_DIR)
        self.history = ChatHistory()
        self._initialize_client()
    
    def _initialize_client(self):
        """Khởi tạo Gemini client"""
        print("🔧 Initializing Gemini LLM...")
        
        api_key = cfg.GEMINI_API_KEY
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            raise ValueError(
                "❌ GEMINI_API_KEY chưa được cấu hình!\\n"
                "Vui lòng set environment variable GEMINI_API_KEY "
                "hoặc cập nhật settings/llm_settings.py"
            )
        
        self.client = genai.Client(api_key=api_key)
        print(f"  ✓ Model: {cfg.GEMINI_MODEL}")
        print(f"  ✓ Chain of Thought: {'Enabled' if cfg.USE_THINKING else 'Disabled'}")
        print("✅ LLM initialized successfully")
    
    def _build_system_prompt(self) -> str:
        """Xây dựng system prompt"""
        return cfg.ROLE_PROMPT + "\\n" + cfg.SAFETY_PROMPT
    
    def _format_rag_context(self, docs: List[Dict]) -> str:
        """Format RAG documents thành context"""
        if not docs:
            return ""
        
        context_parts = []
        for i, doc in enumerate(docs, 1):
            context_parts.append(
                f"[Tài liệu {i} - {doc['source']}]:\\n{doc['text']}"
            )
        
        return "\\n\\n".join(context_parts)
    
    def _format_history_for_gemini(self, history: List[Dict]) -> List[Dict]:
        """Convert internal history format to Gemini format"""
        gemini_history = []
        for msg in history:
            gemini_history.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })
        return gemini_history
    
    def chat(
        self,
        text: str,
        session_id: str = "default",
        use_rag: bool = True
    ) -> str:
        """Chat với LLM"""
        print(f"💬 User: {text}")
        
        self.history.add(session_id, "user", text)
        
        rag_context = ""
        if use_rag:
            docs = self.rag.search(text)
            if docs:
                rag_context = self._format_rag_context(docs)
                print(f"  📚 Retrieved {len(docs)} relevant documents")
        
        system_prompt = self._build_system_prompt()
        
        if rag_context:
            enhanced_prompt = (
                f"{system_prompt}\\n\\n"
                f"=== TÀI LIỆU THAM KHẢO ===\\n{rag_context}\\n"
                f"=== KẾT THÚC TÀI LIỆU ===\\n\\n"
            )
        else:
            enhanced_prompt = system_prompt
        
        history = self.history.get_history(session_id)
        gemini_history = self._format_history_for_gemini(history[:-1])
        
        contents = gemini_history + [{
            "role": "user",
            "parts": [{"text": text}]
        }]
        
        generation_config = types.GenerateContentConfig(
            temperature=cfg.TEMPERATURE,
            max_output_tokens=cfg.MAX_OUTPUT_TOKENS,
            top_p=cfg.TOP_P,
            top_k=cfg.TOP_K,
            system_instruction=enhanced_prompt,
        )
        
        if cfg.USE_THINKING:
            generation_config.thinking_config = types.ThinkingConfig(
                thinking_budget=cfg.THINKING_BUDGET,
                include_thoughts=cfg.INCLUDE_THOUGHTS
            )
        
        try:
            response = self.client.models.generate_content(
                model=cfg.GEMINI_MODEL,
                contents=contents,
                config=generation_config
            )
            
            reply = response.text
            print(f"🤖 Assistant: {reply}")
            
            self.history.add(session_id, "assistant", reply)
            
            return reply
            
        except Exception as e:
            error_msg = f"❌ LLM Error: {str(e)}"
            print(error_msg)
            return f"Xin lỗi, tớ gặp lỗi khi xử lý câu hỏi của cậu. Lỗi: {str(e)}"


def chat_with_llm(text: str, session_id: str = "default") -> str:
    """Helper function để chat với LLM"""
    engine = LLMEngine()
    return engine.chat(text, session_id)


if __name__ == "__main__":
    engine = LLMEngine()
    response = engine.chat("Xin chào! Bạn có thể giúp tôi học toán không?")
    print(f"\\n{'='*50}")
    print(f"Response: {response}")
    print(f"{'='*50}")
