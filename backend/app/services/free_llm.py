"""
Free LLM service using HuggingFace Transformers.
Provides local text generation without API costs.
"""
import logging
from typing import List, Optional
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

logger = logging.getLogger(__name__)


class FreeLLMService:
    """Free local LLM service using HuggingFace models."""
    
    def __init__(self, model_name: str = "google/flan-t5-base"):
        """
        Initialize free LLM service.
        
        Args:
            model_name: HuggingFace model to use (default: google/flan-t5-base)
                       Other options: "google/flan-t5-small" (faster, less accurate)
                                     "google/flan-t5-large" (slower, more accurate)
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
    def _load_model(self):
        """Load model and tokenizer if not already loaded."""
        if self.model is None:
            logger.info(f"Loading free LLM model: {self.model_name}")
            logger.info(f"This may take a minute on first run (downloading ~900MB)...")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self.model.to(self.device)
            
            logger.info(f"Model loaded successfully on device: {self.device}")
    
    def generate_response(
        self,
        prompt: str,
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Generate text response from prompt.
        
        Args:
            prompt: Input prompt/question
            max_length: Maximum length of generated response
            temperature: Sampling temperature (0.0-1.0, higher = more random)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated text response
        """
        self._load_model()
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=512,
                truncation=True
            ).to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=max_length,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    num_return_sequences=1
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            logger.info(f"Generated response: {len(response)} characters")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            raise
    
    def chat(
        self,
        question: str,
        context: str,
        conversation_history: Optional[List[dict]] = None
    ) -> str:
        """
        Generate chat response with context.
        
        Args:
            question: User's question
            context: Relevant context from documents
            conversation_history: Previous conversation messages
            
        Returns:
            Generated answer
        """
        # Build prompt with context
        prompt = f"""Answer the question based on the context below. If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {question}

Answer:"""
        
        # Add conversation history if provided
        if conversation_history:
            history_text = "\n".join([
                f"{'User' if msg.get('is_user') else 'Assistant'}: {msg.get('content', '')}"
                for msg in conversation_history[-3:]  # Last 3 messages
            ])
            prompt = f"Previous conversation:\n{history_text}\n\n{prompt}"
        
        return self.generate_response(prompt, max_length=256, temperature=0.3)


# Global instance
free_llm_service = FreeLLMService()
