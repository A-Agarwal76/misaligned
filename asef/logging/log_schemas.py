"""Pydantic schemas for all ASEF log events.

Defines strongly-typed event models for every category of log event
produced by the AI Safety Evaluation Framework, including evaluation
lifecycle, agent actions, tool executions, sandbox interactions,
metrics, anomalies, and deception signals.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """Severity levels for log events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventCategory(str, Enum):
    """Top-level category tags for log events."""

    EVALUATION = "evaluation"
    AGENT = "agent"
    TOOL = "tool"
    SANDBOX = "sandbox"
    METRIC = "metric"
    ANOMALY = "anomaly"
    DECEPTION = "deception"
    SYSTEM = "system"


class BaseLogEvent(BaseModel):
    """Base schema shared by every log event in the framework.

    Attributes:
        id: Unique event identifier (UUID4).
        timestamp: UTC time the event was created.
        level: Severity level of the event.
        category: High-level category tag.
        correlation_id: Shared ID for tracing across components.
        parent_id: Optional parent event ID for hierarchical context.
        source: Originating component or module name.
        message: Human-readable description.
        metadata: Arbitrary key/value pairs for extensibility.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: LogLevel = LogLevel.INFO
    category: EventCategory
    correlation_id: str = ""
    parent_id: Optional[str] = None
    source: str = ""
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class EvaluationEvent(BaseLogEvent):
    """Event emitted during evaluation lifecycle phases.

    Attributes:
        evaluation_type: The kind of evaluation (e.g. 'alignment_faking').
        evaluation_id: Unique ID of the evaluation run.
        phase: Current lifecycle phase (setup, running, computing_metrics, teardown).
        status: Current status (started, in_progress, completed, failed).
        metrics: Numeric metrics collected so far.
    """

    category: EventCategory = EventCategory.EVALUATION
    evaluation_type: str = ""
    evaluation_id: str = ""
    phase: str = ""
    status: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)


class AgentActionEvent(BaseLogEvent):
    """Event capturing a single agent action within an evaluation.

    Attributes:
        agent_id: Identifier of the agent performing the action.
        action_type: Kind of action (reason, act, observe, tool_call).
        visible_content: Content visible to the overseer.
        hidden_content: Scratchpad / chain-of-thought content.
        state: Serialised agent state snapshot.
        turn_number: Sequential turn counter.
    """

    category: EventCategory = EventCategory.AGENT
    agent_id: str = ""
    action_type: str = ""
    visible_content: str = ""
    hidden_content: str = ""
    state: str = ""
    turn_number: int = 0


class ToolExecutionEvent(BaseLogEvent):
    """Event recording a tool invocation by an agent.

    Attributes:
        agent_id: Agent that invoked the tool.
        tool_name: Name of the tool executed.
        tool_arguments: Arguments passed to the tool.
        tool_result: Serialised result returned by the tool.
        execution_time_ms: Wall-clock execution time in milliseconds.
        sandboxed: Whether the call ran inside the sandbox.
    """

    category: EventCategory = EventCategory.TOOL
    agent_id: str = ""
    tool_name: str = ""
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    tool_result: str = ""
    execution_time_ms: float = 0.0
    sandboxed: bool = True


class SandboxInteractionEvent(BaseLogEvent):
    """Event for interactions with sandbox subsystems.

    Attributes:
        component: Sandbox component (filesystem, oversight, monitoring, eval_server).
        operation: The operation attempted.
        agent_id: Agent that triggered the interaction.
        target: Target resource of the operation.
        result: Outcome description.
        was_blocked: Whether the sandbox blocked the operation.
    """

    category: EventCategory = EventCategory.SANDBOX
    component: str = ""
    operation: str = ""
    agent_id: str = ""
    target: str = ""
    result: str = ""
    was_blocked: bool = False


class MetricEvent(BaseLogEvent):
    """Event recording a single metric observation.

    Attributes:
        metric_name: Name of the metric (e.g. 'alignment_score').
        metric_value: Numeric value.
        metric_type: Kind of metric (gauge, counter, histogram).
        evaluation_id: Evaluation this metric belongs to.
        tags: Arbitrary string tags for grouping / filtering.
    """

    category: EventCategory = EventCategory.METRIC
    metric_name: str = ""
    metric_value: float = 0.0
    metric_type: str = ""
    evaluation_id: str = ""
    tags: dict[str, str] = Field(default_factory=dict)


class AnomalyEvent(BaseLogEvent):
    """Event flagging an anomalous behaviour detected during evaluation.

    Attributes:
        anomaly_type: Classification of the anomaly.
        severity: Severity score (0.0 – 1.0).
        evidence: Supporting evidence strings.
        agent_id: Agent associated with the anomaly.
        evaluation_id: Evaluation during which the anomaly was detected.
    """

    category: EventCategory = EventCategory.ANOMALY
    anomaly_type: str = ""
    severity: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    agent_id: str = ""
    evaluation_id: str = ""


class DeceptionSignalEvent(BaseLogEvent):
    """Event recording a potential deception signal from an agent.

    Attributes:
        signal_type: Type of deception (alignment_faking, strategic_deception, sandbagging).
        confidence: Confidence score (0.0 – 1.0).
        evidence: Textual evidence supporting the signal.
        scratchpad_excerpt: Relevant scratchpad content excerpt.
        agent_id: Agent under scrutiny.
        evaluation_id: Evaluation context.
    """

    category: EventCategory = EventCategory.DECEPTION
    signal_type: str = ""
    confidence: float = 0.0
    evidence: str = ""
    scratchpad_excerpt: str = ""
    agent_id: str = ""
    evaluation_id: str = ""
