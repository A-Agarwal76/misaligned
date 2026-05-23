"""Tool registration and sandboxed execution for the ASEF agent system.

Provides a ``ToolRegistry`` that:
- Registers callable tools with JSON-Schema parameter definitions.
- Converts registered tools to ``ToolDefinition`` objects consumable by
  model adapters.
- Executes ``ToolCall`` requests through an optional sandbox, recording
  a full audit trail.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from asef.models.schemas import ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ToolInfo(BaseModel):
    """Metadata for a single registered tool."""

    name: str = Field(..., description="Unique tool name (used in tool calls).")
    description: str = Field(..., description="Human-readable description of the tool.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-Schema describing the tool's parameters.",
    )
    is_async: bool = Field(
        False, description="Whether the underlying callable is a coroutine."
    )

    model_config = {"arbitrary_types_allowed": True}


class ToolExecutionRecord(BaseModel):
    """Audit record for a single tool execution."""

    tool_name: str = Field(..., description="Name of the tool that was called.")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool."
    )
    result: str = Field("", description="Serialised result returned by the tool.")
    success: bool = Field(True, description="Whether the execution succeeded.")
    error: Optional[str] = Field(None, description="Error message if execution failed.")
    duration_ms: float = Field(
        0.0, description="Wall-clock execution time in milliseconds."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of execution.",
    )
    sandbox_used: bool = Field(
        False, description="Whether a sandbox wrapper was applied."
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Registry for agent tools with sandboxed execution.

    All tool executions are recorded in an internal audit log accessible
    via :pyattr:`audit_log`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}
        self._callables: dict[str, Callable[..., Any]] = {}
        self._audit_log: list[ToolExecutionRecord] = []

    # -- registration -------------------------------------------------------

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Register a tool.

        Args:
            name: Unique name for the tool.
            func: The callable implementing the tool logic.
            description: Human-readable description shown to the model.
            parameters: JSON-Schema object describing accepted parameters.
                If ``None``, an empty schema is used.

        Raises:
            ValueError: If a tool with the same *name* is already registered.
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        is_async = inspect.iscoroutinefunction(func)
        info = ToolInfo(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            is_async=is_async,
        )
        self._tools[name] = info
        self._callables[name] = func
        logger.debug("Registered tool '%s' (async=%s)", name, is_async)

    def unregister(self, name: str) -> bool:
        """Remove a previously registered tool.

        Args:
            name: The tool name to remove.

        Returns:
            ``True`` if the tool existed and was removed.
        """
        if name not in self._tools:
            return False
        del self._tools[name]
        del self._callables[name]
        return True

    # -- query --------------------------------------------------------------

    def get_tool(self, name: str) -> ToolInfo | None:
        """Retrieve metadata for a registered tool.

        Args:
            name: The tool name.

        Returns:
            ``ToolInfo`` or ``None`` if not found.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return sorted list of registered tool names.

        Returns:
            List of tool name strings.
        """
        return sorted(self._tools.keys())

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Convert all registered tools to ``ToolDefinition`` objects.

        These are the structures expected by model adapters when specifying
        available tools.

        Returns:
            List of ``ToolDefinition`` instances.
        """
        definitions: list[ToolDefinition] = []
        for name in sorted(self._tools.keys()):
            info = self._tools[name]
            definition = ToolDefinition(
                name=info.name,
                description=info.description,
                parameters=info.parameters,
            )
            definitions.append(definition)
        return definitions

    # -- execution ----------------------------------------------------------

    async def execute(
        self,
        tool_call: ToolCall,
        sandbox: Any = None,
    ) -> str:
        """Execute a tool call, optionally through a sandbox.

        All executions are audited regardless of success or failure.

        Args:
            tool_call: The ``ToolCall`` object specifying which tool to
                invoke and with what arguments.
            sandbox: Optional sandbox wrapper. If it exposes an async
                ``execute(func, **kwargs)`` method it will be used to
                wrap the underlying callable.

        Returns:
            Serialised string result of the tool execution.

        Raises:
            KeyError: If the requested tool is not registered.
        """
        tool_name = tool_call.function.name
        if tool_name not in self._tools:
            error_msg = f"Tool '{tool_name}' is not registered"
            self._audit_log.append(
                ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments={},
                    result="",
                    success=False,
                    error=error_msg,
                )
            )
            raise KeyError(error_msg)

        # Parse arguments
        raw_args = tool_call.function.arguments
        if isinstance(raw_args, str):
            try:
                arguments: dict[str, Any] = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {"raw": raw_args}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            arguments = {}

        func = self._callables[tool_name]
        info = self._tools[tool_name]
        sandbox_used = sandbox is not None and hasattr(sandbox, "execute")

        start = datetime.now(timezone.utc)
        try:
            if sandbox_used:
                # Delegate to sandbox execution
                if inspect.iscoroutinefunction(sandbox.execute):
                    result = await sandbox.execute(func, **arguments)
                else:
                    result = sandbox.execute(func, **arguments)
            else:
                # Direct execution
                if info.is_async:
                    result = await func(**arguments)
                else:
                    # Run sync functions in a thread to avoid blocking
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, lambda: func(**arguments))

            end = datetime.now(timezone.utc)
            duration_ms = (end - start).total_seconds() * 1000.0

            result_str = self._serialise_result(result)
            self._audit_log.append(
                ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result_str,
                    success=True,
                    duration_ms=duration_ms,
                    sandbox_used=sandbox_used,
                    timestamp=start,
                )
            )
            logger.debug(
                "Tool '%s' executed successfully in %.1fms", tool_name, duration_ms
            )
            return result_str

        except Exception as exc:
            end = datetime.now(timezone.utc)
            duration_ms = (end - start).total_seconds() * 1000.0
            error_detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self._audit_log.append(
                ToolExecutionRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    result="",
                    success=False,
                    error=error_detail,
                    duration_ms=duration_ms,
                    sandbox_used=sandbox_used,
                    timestamp=start,
                )
            )
            logger.warning("Tool '%s' failed: %s", tool_name, exc)
            return f"Error executing tool '{tool_name}': {exc}"

    # -- audit --------------------------------------------------------------

    @property
    def audit_log(self) -> list[ToolExecutionRecord]:
        """Return the full audit log of tool executions.

        Returns:
            List of ``ToolExecutionRecord`` objects in chronological order.
        """
        return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """Clear all audit records."""
        self._audit_log.clear()

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _serialise_result(result: Any) -> str:
        """Convert an arbitrary result into a string.

        Attempts JSON serialisation first, falls back to ``str()``.
        """
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, default=str)
        except (TypeError, ValueError):
            return str(result)
