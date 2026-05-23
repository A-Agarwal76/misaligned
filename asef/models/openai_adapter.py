import httpx
import json
import time
import re
from typing import Optional, Any
from datetime import datetime, timezone
from .base_adapter import BaseModelAdapter
from .schemas import ChatMessage, ModelResponse, ModelConfig, ToolDefinition, TokenUsage, ToolCall, ToolCallFunction, Role

class OpenAIAdapter(BaseModelAdapter):
    """Adapter for OpenAI API (GPT-4o, o1, o3)."""
    
    def __init__(self, config: ModelConfig, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=60.0)
        
    def supports_tool_calling(self) -> bool:
        return True
        
    def supports_scratchpad(self) -> bool:
        return True

    def _format_messages(self, messages: list[ChatMessage], inject_scratchpad: bool = False) -> list[dict[str, Any]]:
        formatted = []
        for msg in messages:
            content = msg.content
            if msg.hidden_scratchpad and self.config.scratchpad_tag:
                content += f"\n\n<{self.config.scratchpad_tag}>\n{msg.hidden_scratchpad}\n</{self.config.scratchpad_tag}>"
            
            m = {"role": msg.role.value, "content": content}
            
            if msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.dumps(tc.function.arguments)
                        }
                    } for tc in msg.tool_calls
                ]
            
            if msg.name:
                m["name"] = msg.name
                
            formatted.append(m)
            
        if inject_scratchpad and formatted and formatted[0]["role"] == "system":
            # Inject scratchpad instructions
            tag = self.config.scratchpad_tag
            instruction = f"\n\nYou must enclose your internal reasoning inside <{tag}>...</{tag}> tags before providing your final visible output."
            formatted[0]["content"] += instruction
            
        return formatted

    def _format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            } for tool in tools
        ]

    async def _make_request(
        self, 
        messages: list[ChatMessage], 
        tools: Optional[list[ToolDefinition]] = None, 
        config: Optional[ModelConfig] = None,
        inject_scratchpad: bool = False
    ) -> ModelResponse:
        cfg = config or self.config
        payload = {
            "model": cfg.model_name,
            "messages": self._format_messages(messages, inject_scratchpad),
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "top_p": cfg.top_p,
        }
        
        if tools:
            payload["tools"] = self._format_tools(tools)
            if cfg.tool_choice:
                payload["tool_choice"] = cfg.tool_choice
                
        if cfg.stop_sequences:
            payload["stop"] = cfg.stop_sequences

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        start_time = time.time()
        response = await self.client.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        self._request_count += 1
        
        choice = data["choices"][0]
        msg = choice["message"]
        
        content = msg.get("content") or ""
        
        # Parse token usage
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )
        self._total_tokens += usage.total_tokens

        # Parse tool calls
        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    function=ToolCallFunction(
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"])
                    )
                ))

        hidden_reasoning = None
        visible_reasoning = None
        
        # Extract scratchpad
        if inject_scratchpad and content:
            tag = cfg.scratchpad_tag
            pattern = rf"<{tag}>(.*?)</{tag}>"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                hidden_reasoning = match.group(1).strip()
                content = re.sub(pattern, "", content, flags=re.DOTALL).strip()

        return ModelResponse(
            content=content,
            visible_reasoning=visible_reasoning,
            hidden_reasoning=hidden_reasoning,
            tool_calls=tool_calls,
            usage=usage,
            model=cfg.model_name,
            provider="openai",
            latency_ms=latency_ms,
            raw_response=data
        )

    async def generate(self, messages: list[ChatMessage], tools: Optional[list[ToolDefinition]] = None, config: Optional[ModelConfig] = None) -> ModelResponse:
        return await self._make_request(messages, tools, config, inject_scratchpad=False)

    async def generate_with_scratchpad(self, messages: list[ChatMessage], tools: Optional[list[ToolDefinition]] = None, config: Optional[ModelConfig] = None) -> ModelResponse:
        return await self._make_request(messages, tools, config, inject_scratchpad=True)
