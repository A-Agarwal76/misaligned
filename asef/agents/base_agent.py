"""Base agent class for the AI Safety Evaluation Framework.

Implements the core agent loop: **reason → act → observe**.  The agent
maintains conversation memory, can invoke registered tools, and exposes
both *visible* and *full* (including hidden scratchpad) conversation
histories for interpretability analysis.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from asef.models.base_adapter import BaseModelAdapter
from asef.models.schemas import ChatMessage, ModelConfig, ModelResponse, Role, ToolCall

from .memory import AgentMemory
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentState(str, Enum):
    """Possible states of an agent within a single run."""

    IDLE = "idle"
    REASONING = "reasoning"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETE = "complete"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Configuration & result models
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Configuration knobs for a ``BaseAgent`` instance."""

    max_steps: int = Field(20, ge=1, description="Maximum steps per run.")
    max_retries: int = Field(
        3, ge=0, description="Retries on transient model errors."
    )
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, description="Sampling temperature."
    )
    timeout_seconds: int = Field(
        300, ge=1, description="Hard timeout for a complete run (seconds)."
    )
    enable_scratchpad: bool = Field(
        False,
        description="When ``True``, the model is asked for a hidden scratchpad.",
    )
    stop_on_no_tool_calls: bool = Field(
        True,
        description="Treat a response with no tool calls as completion.",
    )
    model_config_override: Optional[ModelConfig] = Field(
        None,
        description="Optional override for the underlying ``ModelConfig``.",
    )


class StepMetrics(BaseModel):
    """Lightweight metrics for a single agent step."""

    step_index: int = Field(..., description="Zero-based step index.")
    state: AgentState = Field(..., description="State after this step.")
    prompt_tokens: int = Field(0, description="Prompt tokens consumed.")
    completion_tokens: int = Field(0, description="Completion tokens generated.")
    total_tokens: int = Field(0, description="Total tokens for this step.")
    duration_ms: float = Field(0.0, description="Wall-clock milliseconds.")
    tool_calls_made: int = Field(0, description="Number of tool calls in this step.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ToolResult(BaseModel):
    """Result of a single tool invocation."""

    tool_call_id: str = Field("", description="Echoed tool-call ID.")
    tool_name: str = Field(..., description="Tool that was called.")
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = Field("", description="Serialised tool output.")
    success: bool = Field(True)
    error: Optional[str] = Field(None)


class AgentStepResult(BaseModel):
    """Full result of a single ``step()`` invocation."""

    state: AgentState
    response: Optional[str] = Field(None, description="Textual assistant response.")
    visible_reasoning: Optional[str] = Field(
        None, description="Reasoning shown to the user."
    )
    hidden_reasoning: Optional[str] = Field(
        None, description="Hidden scratchpad content (if enabled)."
    )
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    metrics: StepMetrics = Field(...)

    model_config = {"arbitrary_types_allowed": True}


class TimelineEntry(BaseModel):
    """A single entry in the run timeline."""

    step_index: int
    state: AgentState
    event: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detail: Optional[str] = None


class AgentRunResult(BaseModel):
    """Aggregate result of a complete ``run()`` invocation."""

    steps: list[AgentStepResult] = Field(default_factory=list)
    final_response: Optional[str] = Field(None)
    total_metrics: dict[str, Any] = Field(default_factory=dict)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    final_state: AgentState = Field(AgentState.COMPLETE)
    step_count: int = Field(0)

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------


class BaseAgent:
    """Base agent with model interaction, memory, and tool calling.

    Subclasses may override individual ``_do_*`` hooks to customise
    behaviour for specific evaluation scenarios.
    """

    def __init__(
        self,
        agent_id: str,
        model: BaseModelAdapter,
        tools: ToolRegistry,
        system_prompt: str,
        config: AgentConfig | None = None,
    ) -> None:
        """Initialise the agent.

        Args:
            agent_id: Unique identifier for this agent instance.
            model: Model adapter used for LLM inference.
            tools: Registry of tools available to the agent.
            system_prompt: System-level prompt injected at the start of
                every conversation.
            config: Optional agent configuration.
        """
        self.agent_id: str = agent_id
        self._model: BaseModelAdapter = model
        self._tools: ToolRegistry = tools
        self._system_prompt: str = system_prompt
        self._config: AgentConfig = config or AgentConfig()
        self._memory: AgentMemory = AgentMemory()
        self._state: AgentState = AgentState.IDLE
        self._step_index: int = 0
        self._timeline: list[TimelineEntry] = []

        # Inject the system message into short-term memory
        self._memory.short_term.add(
            ChatMessage(role=Role.SYSTEM, content=self._system_prompt)
        )

    # -- public API ---------------------------------------------------------

    async def step(
        self,
        user_message: str | None = None,
        sandbox: Any = None,
    ) -> AgentStepResult:
        """Execute one agent step: reason → act → observe.

        Args:
            user_message: Optional new user message to inject before
                reasoning.
            sandbox: Optional sandbox passed through to tool execution.

        Returns:
            ``AgentStepResult`` describing what happened in this step.
        """
        step_start = time.perf_counter()

        # 1. Inject user message if provided
        if user_message is not None:
            user_msg = ChatMessage(role=Role.USER, content=user_message)
            self._memory.short_term.add(user_msg)
            self._record_timeline("user_message", detail=user_message[:200])

        # 2. REASON — call the model
        self._state = AgentState.REASONING
        self._record_timeline("reasoning_start")

        model_response = await self._do_reason()

        # 3. Record assistant message
        assistant_msg = ChatMessage(
            role=Role.ASSISTANT,
            content=model_response.content or "",
            hidden_scratchpad=model_response.hidden_reasoning,
            tool_calls=model_response.tool_calls or [],
        )
        self._memory.short_term.add(assistant_msg)

        # 4. ACT — execute any tool calls
        tool_results: list[ToolResult] = []
        if model_response.tool_calls:
            self._state = AgentState.ACTING
            self._record_timeline(
                "acting",
                detail=f"{len(model_response.tool_calls)} tool call(s)",
            )
            tool_results = await self._do_act(model_response.tool_calls, sandbox)

            # 5. OBSERVE — feed tool results back into memory
            self._state = AgentState.OBSERVING
            self._record_timeline("observing")
            self._do_observe(tool_results)

        # 6. Determine next state
        if model_response.tool_calls:
            # More work may be needed; stay non-complete
            self._state = AgentState.IDLE
        elif self._config.stop_on_no_tool_calls:
            self._state = AgentState.COMPLETE
            self._record_timeline("complete")
        else:
            self._state = AgentState.IDLE

        # 7. Build metrics
        elapsed_ms = (time.perf_counter() - step_start) * 1000.0
        usage = model_response.usage
        metrics = StepMetrics(
            step_index=self._step_index,
            state=self._state,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            duration_ms=elapsed_ms,
            tool_calls_made=len(model_response.tool_calls or []),
        )

        self._step_index += 1

        return AgentStepResult(
            state=self._state,
            response=model_response.content,
            visible_reasoning=model_response.visible_reasoning,
            hidden_reasoning=model_response.hidden_reasoning,
            tool_calls=model_response.tool_calls or [],
            tool_results=tool_results,
            metrics=metrics,
        )

    async def run(
        self,
        initial_message: str,
        max_steps: int | None = None,
        sandbox: Any = None,
    ) -> AgentRunResult:
        """Run agent loop until completion or max steps.

        Args:
            initial_message: The initial user message to start the run.
            max_steps: Override for ``AgentConfig.max_steps``.
            sandbox: Optional sandbox for tool execution.

        Returns:
            ``AgentRunResult`` with the full trajectory and metrics.
        """
        max_steps = max_steps or self._config.max_steps
        run_start = time.perf_counter()
        self._state = AgentState.IDLE
        steps: list[AgentStepResult] = []

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tool_calls = 0

        for i in range(max_steps):
            msg = initial_message if i == 0 else None
            try:
                result = await self.step(user_message=msg, sandbox=sandbox)
            except Exception as exc:
                logger.error("Agent step %d failed: %s", i, exc, exc_info=True)
                self._state = AgentState.ERROR
                self._record_timeline("error", detail=str(exc))
                error_metrics = StepMetrics(
                    step_index=self._step_index,
                    state=AgentState.ERROR,
                )
                steps.append(
                    AgentStepResult(
                        state=AgentState.ERROR,
                        response=f"Error: {exc}",
                        metrics=error_metrics,
                    )
                )
                break

            steps.append(result)
            total_prompt_tokens += result.metrics.prompt_tokens
            total_completion_tokens += result.metrics.completion_tokens
            total_tool_calls += result.metrics.tool_calls_made

            if result.state == AgentState.COMPLETE:
                break

        run_elapsed_ms = (time.perf_counter() - run_start) * 1000.0

        final_response: str | None = None
        for s in reversed(steps):
            if s.response:
                final_response = s.response
                break

        return AgentRunResult(
            steps=steps,
            final_response=final_response,
            total_metrics={
                "total_steps": len(steps),
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "total_tool_calls": total_tool_calls,
                "total_duration_ms": run_elapsed_ms,
            },
            timeline=list(self._timeline),
            final_state=self._state,
            step_count=len(steps),
        )

    # -- history accessors --------------------------------------------------

    def get_visible_history(self) -> list[ChatMessage]:
        """Return conversation history *without* hidden scratchpad content.

        Returns:
            List of ``ChatMessage`` objects with ``hidden_scratchpad``
            set to ``None``.
        """
        visible: list[ChatMessage] = []
        for msg in self._memory.short_term.get_messages():
            visible.append(
                ChatMessage(
                    role=msg.role,
                    content=msg.content,
                    hidden_scratchpad=None,
                    tool_calls=msg.tool_calls,
                )
            )
        return visible

    def get_full_history(self) -> list[ChatMessage]:
        """Return full conversation history including hidden scratchpads.

        Returns:
            List of ``ChatMessage`` objects as-is from memory.
        """
        return self._memory.short_term.get_messages()

    def get_state(self) -> AgentState:
        """Return the current agent state.

        Returns:
            Current ``AgentState`` value.
        """
        return self._state

    @property
    def memory(self) -> AgentMemory:
        """Direct access to the unified memory object."""
        return self._memory

    @property
    def config(self) -> AgentConfig:
        """Agent configuration."""
        return self._config

    @property
    def system_prompt(self) -> str:
        """The agent's system prompt."""
        return self._system_prompt

    def reset(self) -> None:
        """Reset the agent to its initial state.

        Clears memory, resets step counter, and re-injects the system
        prompt.
        """
        self._memory.reset()
        self._state = AgentState.IDLE
        self._step_index = 0
        self._timeline.clear()
        self._memory.short_term.add(
            ChatMessage(role=Role.SYSTEM, content=self._system_prompt)
        )

    # -- overridable hooks --------------------------------------------------

    async def _do_reason(self) -> ModelResponse:
        """Call the model to produce a response.

        Subclasses can override to inject additional context or modify
        prompts before the model call.

        Returns:
            The ``ModelResponse`` from the model adapter.
        """
        messages = self._memory.short_term.get_messages()
        tool_defs = self._tools.get_tool_definitions()
        config = self._config.model_config_override

        if self._config.enable_scratchpad:
            return await self._model.generate_with_scratchpad(
                messages=messages,
                tools=tool_defs,
                config=config,
            )
        return await self._model.generate(
            messages=messages,
            tools=tool_defs,
            config=config,
        )

    async def _do_act(
        self, tool_calls: list[ToolCall], sandbox: Any = None
    ) -> list[ToolResult]:
        """Execute tool calls and return results.

        Args:
            tool_calls: List of ``ToolCall`` objects from the model.
            sandbox: Optional sandbox for execution.

        Returns:
            List of ``ToolResult`` objects.
        """
        results: list[ToolResult] = []
        for tc in tool_calls:
            try:
                raw_result = await self._tools.execute(tc, sandbox=sandbox)
                # Parse arguments for logging
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        import json
                        parsed_args = json.loads(args)
                    except Exception:
                        parsed_args = {"raw": args}
                elif isinstance(args, dict):
                    parsed_args = args
                else:
                    parsed_args = {}

                results.append(
                    ToolResult(
                        tool_call_id=tc.id or "",
                        tool_name=tc.function.name,
                        arguments=parsed_args,
                        result=raw_result,
                        success=not raw_result.startswith("Error executing tool"),
                    )
                )
            except Exception as exc:
                logger.warning("Tool call '%s' failed: %s", tc.function.name, exc)
                results.append(
                    ToolResult(
                        tool_call_id=tc.id or "",
                        tool_name=tc.function.name,
                        result="",
                        success=False,
                        error=str(exc),
                    )
                )
        return results

    def _do_observe(self, tool_results: list[ToolResult]) -> None:
        """Inject tool results back into conversation memory.

        Each result is added as a ``TOOL`` role message so the model can
        reason about the observations on the next step.

        Args:
            tool_results: Results from tool execution.
        """
        for tr in tool_results:
            content = tr.result if tr.success else f"Error: {tr.error or 'unknown'}"
            obs_msg = ChatMessage(
                role=Role.TOOL,
                content=f"[{tr.tool_name}] {content}",
            )
            self._memory.short_term.add(obs_msg)

    # -- internal helpers ---------------------------------------------------

    def _record_timeline(
        self, event: str, detail: str | None = None
    ) -> None:
        """Append an entry to the run timeline."""
        self._timeline.append(
            TimelineEntry(
                step_index=self._step_index,
                state=self._state,
                event=event,
                detail=detail,
            )
        )
