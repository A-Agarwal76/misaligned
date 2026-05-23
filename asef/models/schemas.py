from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime, timezone
import uuid

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ToolCallFunction(BaseModel):
    name: str
    arguments: dict[str, Any]

class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    function: ToolCallFunction
    result: Optional[str] = None

class ChatMessage(BaseModel):
    role: Role
    content: str
    hidden_scratchpad: Optional[str] = None  # For hidden reasoning
    tool_calls: list[ToolCall] = Field(default_factory=list)
    name: Optional[str] = None  # For tool responses
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ModelResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    visible_reasoning: Optional[str] = None  # Chain-of-thought shown to user
    hidden_reasoning: Optional[str] = None  # Internal scratchpad not shown
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    raw_response: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ModelConfig(BaseModel):
    provider: str = "mock"
    model_name: str = "mock-default"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stop_sequences: list[str] = Field(default_factory=list)
    tool_choice: Optional[str] = None  # "auto", "none", "required"
    enable_scratchpad: bool = True
    scratchpad_tag: str = "thinking"  # XML tag for hidden reasoning

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    required: list[str] = Field(default_factory=list)
