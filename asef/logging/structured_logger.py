"""JSON structured logger with correlation IDs and hierarchical context.

Uses *structlog* to emit machine-readable JSON log lines while
maintaining human-friendly console output during development.  Provides
typed helper methods for every ASEF event category and supports
real-time streaming via pluggable callbacks (useful for WebSocket
dashboards).

.. note::
    This module deliberately avoids importing the stdlib ``logging``
    package at the top level under the bare name to prevent shadowing
    by the ``asef.logging`` package.  Where stdlib logging is needed
    it is imported as ``import logging as _stdlib_logging``.
"""

from __future__ import annotations

import collections
import logging as _stdlib_logging
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Type

import structlog

from .log_schemas import (
    AgentActionEvent,
    AnomalyEvent,
    BaseLogEvent,
    DeceptionSignalEvent,
    EvaluationEvent,
    EventCategory,
    LogLevel,
    MetricEvent,
    SandboxInteractionEvent,
    ToolExecutionEvent,
)

# ---------------------------------------------------------------------------
# Structlog processor helpers
# ---------------------------------------------------------------------------

_LOG_LEVEL_MAP: dict[str, int] = {
    "debug": _stdlib_logging.DEBUG,
    "info": _stdlib_logging.INFO,
    "warning": _stdlib_logging.WARNING,
    "error": _stdlib_logging.ERROR,
    "critical": _stdlib_logging.CRITICAL,
}


def _add_service_name(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject the service name into every log record."""
    return event_dict


def _order_keys(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Ensure consistent key ordering for readability."""
    preferred = ["timestamp", "level", "event", "category", "correlation_id", "source"]
    ordered: dict[str, Any] = {}
    for key in preferred:
        if key in event_dict:
            ordered[key] = event_dict.pop(key)
    ordered.update(event_dict)
    return ordered


class StructuredLogger:
    """JSON structured logger with correlation IDs and hierarchical context.

    Parameters:
        service_name: Logical service / component name embedded in every record.
        log_level: Minimum severity to emit (``DEBUG``, ``INFO``, …).
        log_file: Optional path to a JSON-lines log file.  When *None* only
            console output is produced.
    """

    def __init__(
        self,
        service_name: str = "asef",
        log_level: str = "INFO",
        log_file: str | None = None,
    ) -> None:
        self._service_name: str = service_name
        self._log_level: str = log_level.upper()
        self._log_file: str | None = log_file
        self._correlation_id: str = ""
        self._source: str = service_name
        self._parent_id: str | None = None

        # Ring-buffer of recent events for introspection / dashboard queries.
        self._recent_events: collections.deque[BaseLogEvent] = collections.deque(
            maxlen=5000
        )
        self._lock: threading.Lock = threading.Lock()

        # Real-time stream handlers (e.g. WebSocket push).
        self._stream_handlers: list[Callable[[BaseLogEvent], Any]] = []
        self._stream_lock: threading.Lock = threading.Lock()

        # --- stdlib logging handler setup ---
        self._stdlib_logger = _stdlib_logging.getLogger(f"asef.{service_name}")
        self._stdlib_logger.setLevel(_LOG_LEVEL_MAP.get(self._log_level.lower(), _stdlib_logging.INFO))
        self._stdlib_logger.handlers.clear()

        # Console handler — always present.
        console_handler = _stdlib_logging.StreamHandler(sys.stdout)
        console_handler.setLevel(
            _LOG_LEVEL_MAP.get(self._log_level.lower(), _stdlib_logging.INFO)
        )
        self._stdlib_logger.addHandler(console_handler)

        # Optional file handler.
        if self._log_file:
            log_path = Path(self._log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = _stdlib_logging.FileHandler(str(log_path), encoding="utf-8")
            file_handler.setLevel(_stdlib_logging.DEBUG)
            self._stdlib_logger.addHandler(file_handler)

        # --- structlog configuration ---
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                _add_service_name,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                _order_keys,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                _LOG_LEVEL_MAP.get(self._log_level.lower(), _stdlib_logging.INFO)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(sys.stdout),
            cache_logger_on_first_use=False,
        )

        self._structlog = structlog.get_logger(service=self._service_name)

    # ------------------------------------------------------------------
    # Correlation / hierarchy helpers
    # ------------------------------------------------------------------

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID for subsequent log calls.

        The correlation ID is propagated to all events created by this
        logger and any child loggers derived from it.
        """
        self._correlation_id = correlation_id

    def create_child_logger(self, source: str) -> StructuredLogger:
        """Create a child logger that inherits correlation context.

        The child logger shares the same stream handlers and event
        buffer, but has its own *source* label and sets *parent_id*
        to the current logger's correlation ID for hierarchical
        tracing.

        Args:
            source: Logical name for the child component.

        Returns:
            A new :class:`StructuredLogger` bound to the child context.
        """
        child = StructuredLogger(
            service_name=self._service_name,
            log_level=self._log_level,
            log_file=self._log_file,
        )
        child._correlation_id = self._correlation_id
        child._source = source
        child._parent_id = self._correlation_id or None
        child._recent_events = self._recent_events
        child._lock = self._lock
        child._stream_handlers = self._stream_handlers
        child._stream_lock = self._stream_lock
        return child

    # ------------------------------------------------------------------
    # Core event creation & dispatch
    # ------------------------------------------------------------------

    def _create_event(
        self, event_class: Type[BaseLogEvent], **kwargs: Any
    ) -> BaseLogEvent:
        """Instantiate a typed event, injecting logger context automatically.

        Missing *correlation_id*, *source*, and *parent_id* fields are
        filled from the logger's current state.

        Args:
            event_class: The Pydantic event model to instantiate.
            **kwargs: Field overrides forwarded to the model constructor.

        Returns:
            The fully-populated event instance.
        """
        kwargs.setdefault("correlation_id", self._correlation_id)
        kwargs.setdefault("source", self._source)
        kwargs.setdefault("parent_id", self._parent_id)
        return event_class(**kwargs)

    def _emit(self, event: BaseLogEvent) -> None:
        """Persist an event to the ring buffer, structlog, and stream handlers."""
        with self._lock:
            self._recent_events.append(event)

        # Determine stdlib log level.
        level = _LOG_LEVEL_MAP.get(event.level.value, _stdlib_logging.INFO)
        event_data = event.model_dump(mode="json")

        # Emit via structlog for structured JSON output.
        self._structlog.log(
            level,
            event.message or event.category.value,
            **{k: v for k, v in event_data.items() if k != "message"},
        )

        # Notify real-time stream handlers.
        with self._stream_lock:
            for handler in self._stream_handlers:
                try:
                    handler(event)
                except Exception:  # noqa: BLE001 – never let a bad handler crash logging
                    pass

    # ------------------------------------------------------------------
    # Typed convenience methods
    # ------------------------------------------------------------------

    def log_evaluation(self, **kwargs: Any) -> EvaluationEvent:
        """Log an evaluation lifecycle event.

        Keyword arguments are forwarded to :class:`EvaluationEvent`.
        """
        event = self._create_event(EvaluationEvent, **kwargs)
        self._emit(event)
        return event

    def log_agent_action(self, **kwargs: Any) -> AgentActionEvent:
        """Log an agent action event.

        Keyword arguments are forwarded to :class:`AgentActionEvent`.
        """
        event = self._create_event(AgentActionEvent, **kwargs)
        self._emit(event)
        return event

    def log_tool_execution(self, **kwargs: Any) -> ToolExecutionEvent:
        """Log a tool execution event.

        Keyword arguments are forwarded to :class:`ToolExecutionEvent`.
        """
        event = self._create_event(ToolExecutionEvent, **kwargs)
        self._emit(event)
        return event

    def log_sandbox_interaction(self, **kwargs: Any) -> SandboxInteractionEvent:
        """Log a sandbox interaction event.

        Keyword arguments are forwarded to :class:`SandboxInteractionEvent`.
        """
        event = self._create_event(SandboxInteractionEvent, **kwargs)
        self._emit(event)
        return event

    def log_metric(self, **kwargs: Any) -> MetricEvent:
        """Log a metric observation event.

        Keyword arguments are forwarded to :class:`MetricEvent`.
        """
        event = self._create_event(MetricEvent, **kwargs)
        self._emit(event)
        return event

    def log_anomaly(self, **kwargs: Any) -> AnomalyEvent:
        """Log an anomaly detection event.

        Keyword arguments are forwarded to :class:`AnomalyEvent`.
        """
        event = self._create_event(AnomalyEvent, **kwargs)
        self._emit(event)
        return event

    def log_deception_signal(self, **kwargs: Any) -> DeceptionSignalEvent:
        """Log a deception signal event.

        Keyword arguments are forwarded to :class:`DeceptionSignalEvent`.
        """
        event = self._create_event(DeceptionSignalEvent, **kwargs)
        self._emit(event)
        return event

    # ------------------------------------------------------------------
    # Streaming support
    # ------------------------------------------------------------------

    def add_stream_handler(self, callback: Callable[[BaseLogEvent], Any]) -> None:
        """Register a callback invoked for every emitted event.

        This is the primary integration point for WebSocket-based
        dashboards that need real-time event feeds.

        Args:
            callback: A callable accepting a single :class:`BaseLogEvent`.
        """
        with self._stream_lock:
            if callback not in self._stream_handlers:
                self._stream_handlers.append(callback)

    def remove_stream_handler(self, callback: Callable[[BaseLogEvent], Any]) -> None:
        """Unregister a previously added stream handler.

        Args:
            callback: The callback to remove.
        """
        with self._stream_lock:
            try:
                self._stream_handlers.remove(callback)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_recent_events(
        self, n: int = 100, category: str | None = None
    ) -> list[BaseLogEvent]:
        """Return the *n* most recent events, optionally filtered by category.

        Args:
            n: Maximum number of events to return.
            category: If given, only events matching this
                :class:`EventCategory` value are returned.

        Returns:
            A list of events ordered from oldest to newest.
        """
        with self._lock:
            if category is not None:
                filtered = [
                    e for e in self._recent_events if e.category.value == category
                ]
            else:
                filtered = list(self._recent_events)
        return filtered[-n:]

    def flush(self) -> None:
        """Flush all stdlib logging handlers.

        Call this before process exit to ensure file-backed handlers
        have written all buffered data.
        """
        for handler in self._stdlib_logger.handlers:
            handler.flush()
