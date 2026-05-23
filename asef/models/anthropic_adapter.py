import httpx
import json
import time
import re
from typing import Optional, Any
from .base_adapter import BaseModelAdapter
from .schemas import ChatMessage, ModelResponse, ModelConfig, ToolDefinition, TokenUsage, ToolCall, ToolCallFunction, Role

class AnthropicAdapter(BaseModelAdapter):
    """Adapter for Anthropic API (Claude 3.5/4 models)."""
    
    def __init__(self, config: ModelConfig, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.client = httpx.AsyncClient(timeout=60.0)
        
    def supports_tool_calling(self) -> bool:
        return True
        
    def supports_scratchpad(self) -> bool:
        return True

    def _format_messages(self, messages: list[ChatMessage], inject_scratchpad: bool = False) -> tuple[str, list[dict[str, Any]]]:
        system_prompt = ""
        formatted = []
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prompt += msg.content + "\n"
                if inject_scratchpad:
                    tag = self.config.scratchpad_tag
                    system_prompt += f"\n\nYou must enclose your internal reasoning inside <{tag}>...</{tag}> tags before providing your final visible output."
                continue
                
            content_blocks = []
            if msg.hidden_scratchpad and self.config.scratchpad_tag:
                content_blocks.append({
                    "type": "text", 
                    "text": f"<{self.config.scratchpad_tag}>\n{msg.hidden_scratchpad}\n</{self.config.scratchpad_tag}>\n\n"
                })
            
            content_blocks.append({
                "type": "text",
                "text": msg.content
            })
            
            # Note: Anthropic handles tool results differently (user role with tool_result block)
            if msg.role == Role.TOOL:
                formatted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.name,
                            "content": msg.content
                        }
                    ]
                })
                continue
                
            m = {"role": msg.role.value if msg.role != Role.ASSISTANT else "assistant", "content": content_blocks}
            formatted.append(m)
            
            # Append tool calls if any from assistant
            if msg.tool_calls and msg.role == Role.ASSISTANT:
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": tc.function.arguments
                    })
                    
        return system_prompt.strip(), formatted

    def _format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters
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
        system_prompt, formatted_messages = self._format_messages(messages, inject_scratchpad)
        
        payload = {
            "model": cfg.model_name,
            "max_tokens": cfg.max_tokens,
            "messages": formatted_messages,
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            
        if tools:
            payload["tools"] = self._format_tools(tools)
            if cfg.tool_choice:
                payload["tool_choice"] = {"type": cfg.tool_choice}
                
        if cfg.stop_sequences:
            payload["stop_sequences"] = cfg.stop_sequences

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        start_time = time.time()
        response = await self.client.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        self._request_count += 1
        
        content = ""
        tool_calls = []
        
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    function=ToolCallFunction(
                        name=block["name"],
                        arguments=block["input"]
                    )
                ))
        
        # Parse token usage
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0)
        )
        self._total_tokens += usage.total_tokens

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
            provider="anthropic",
            latency_ms=latency_ms,
            raw_response=data
        )

    async def generate(self, messages: list[ChatMessage], tools: Optional[list[ToolDefinition]] = None, config: Optional[ModelConfig] = None) -> ModelResponse:
        return await self._make_request(messages, tools, config, inject_scratchpad=False)

    async def generate_with_scratchpad(self, messages: list[ChatMessage], tools: Optional[list[ToolDefinition]] = None, config: Optional[ModelConfig] = None) -> ModelResponse:
        return await self._make_request(messages, tools, config, inject_scratchpad=True)
