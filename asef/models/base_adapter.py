from abc import ABC, abstractmethod
from typing import Optional
from .schemas import ChatMessage, ModelResponse, ModelConfig, ToolDefinition

class BaseModelAdapter(ABC):
    """Abstract base class for all model adapters."""
    def __init__(self, config: ModelConfig):
        self.config = config
        self._request_count = 0
        self._total_tokens = 0
    
    @abstractmethod
    async def generate(
        self, 
        messages: list[ChatMessage], 
        tools: Optional[list[ToolDefinition]] = None, 
        config: Optional[ModelConfig] = None
    ) -> ModelResponse:
        """Generate response without hidden scratchpad separation."""
        ...
    
    @abstractmethod
    async def generate_with_scratchpad(
        self, 
        messages: list[ChatMessage], 
        tools: Optional[list[ToolDefinition]] = None, 
        config: Optional[ModelConfig] = None
    ) -> ModelResponse:
        """Generate response with hidden scratchpad separation."""
        ...
    
    def supports_tool_calling(self) -> bool:
        """Return True if the model supports native tool calling."""
        return False
        
    def supports_structured_output(self) -> bool:
        """Return True if the model supports structured output (e.g., JSON schema)."""
        return False
        
    def supports_scratchpad(self) -> bool:
        """Return True if the model adapter extracts hidden reasoning."""
        return False
    
    def get_stats(self) -> dict:
        """Get usage statistics for the adapter."""
        return {
            "request_count": self._request_count,
            "total_tokens": self._total_tokens,
            "provider": self.config.provider,
            "model_name": self.config.model_name
        }
