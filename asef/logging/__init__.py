"""ASEF Logging Pipeline — structured event logging, persistence, and export.

This package provides the full logging pipeline for the AI Safety
Evaluation Framework:

* **Schemas** — Pydantic models for every event category
  (:class:`BaseLogEvent`, :class:`EvaluationEvent`, …).
* **StructuredLogger** — JSON structured logger built on *structlog*
  with correlation IDs, hierarchical child loggers, and real-time
  streaming hooks.
* **DatabaseLogger** — Async SQLAlchemy 2.0 persistence layer for
  evaluation data.
* **LogExporter** — Export evaluation data to JSON, CSV, and
  self-contained dark-themed HTML reports.

.. note::
    This package is named ``asef.logging`` which shadows Python's
    built-in :mod:`logging` module when imported as a bare name.
    All internal references to the stdlib logger use
    ``import logging as _stdlib_logging`` to avoid the conflict.
    External consumers should import from this package via its
    fully-qualified name (``from asef.logging import …``) or use
    ``import logging`` **before** any ``asef`` imports so that the
    stdlib module is already cached in ``sys.modules``.
"""

from __future__ import annotations

# -- Schemas ---------------------------------------------------------------
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

# -- Loggers ---------------------------------------------------------------
from .structured_logger import StructuredLogger
from .db_logger import (
    DatabaseLogger,
    # ORM models (re-exported for advanced consumers)
    AgentActionRecord,
    AnomalyRecord,
    Base,
    EvaluationRecord,
    MetricRecord,
)

# -- Exporters -------------------------------------------------------------
from .exporters import LogExporter

__all__: list[str] = [
    # Schemas
    "LogLevel",
    "EventCategory",
    "BaseLogEvent",
    "EvaluationEvent",
    "AgentActionEvent",
    "ToolExecutionEvent",
    "SandboxInteractionEvent",
    "MetricEvent",
    "AnomalyEvent",
    "DeceptionSignalEvent",
    # Loggers
    "StructuredLogger",
    "DatabaseLogger",
    # ORM models
    "Base",
    "EvaluationRecord",
    "AgentActionRecord",
    "MetricRecord",
    "AnomalyRecord",
    # Exporters
    "LogExporter",
]
