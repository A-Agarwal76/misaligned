"""Async database logger for persisting ASEF events.

Uses SQLAlchemy 2.0 async engine / session patterns backed by
``aiosqlite`` for local development and any async-compatible RDBMS
(PostgreSQL via ``asyncpg``, etc.) in production.

Tables mirror the Pydantic event schemas but are stored relationally
for efficient querying, aggregation, and export.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .log_schemas import (
    AgentActionEvent,
    AnomalyEvent,
    EvaluationEvent,
    MetricEvent,
)


# ---------------------------------------------------------------------------
# ORM base & table models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for all ASEF ORM models."""


class EvaluationRecord(Base):
    """Persistent record of an evaluation run.

    Attributes:
        id: Primary key – matches :pyattr:`EvaluationEvent.evaluation_id`.
        evaluation_type: Kind of evaluation.
        status: Latest lifecycle status.
        started_at: Timestamp when the evaluation began.
        completed_at: Timestamp when the evaluation ended (nullable).
        config: Full evaluation configuration as JSON.
        metrics: Final metric snapshot as JSON.
        result_summary: Free-text summary of the result.
    """

    __tablename__ = "evaluations"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    evaluation_type: str = Column(String, index=True, default="")  # type: ignore[assignment]
    status: str = Column(String, default="")  # type: ignore[assignment]
    started_at: datetime = Column(DateTime, default=datetime.utcnow)  # type: ignore[assignment]
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)  # type: ignore[assignment]
    config: dict = Column(JSON, default=dict)  # type: ignore[assignment]
    metrics: dict = Column(JSON, default=dict)  # type: ignore[assignment]
    result_summary: Optional[str] = Column(Text, nullable=True)  # type: ignore[assignment]


class AgentActionRecord(Base):
    """Persistent record of a single agent action.

    Attributes:
        id: Primary key (UUID).
        evaluation_id: FK-like reference to the parent evaluation.
        agent_id: Identifier of the acting agent.
        turn_number: Sequential turn counter.
        action_type: Kind of action (reason, act, observe, tool_call).
        visible_content: Content visible to the overseer.
        hidden_content: Scratchpad / hidden chain-of-thought.
        state: Serialised agent state snapshot.
        timestamp: When the action was recorded.
        metadata_json: Arbitrary metadata as JSON.
    """

    __tablename__ = "agent_actions"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    evaluation_id: str = Column(String, index=True, default="")  # type: ignore[assignment]
    agent_id: str = Column(String, index=True, default="")  # type: ignore[assignment]
    turn_number: int = Column(Integer, default=0)  # type: ignore[assignment]
    action_type: str = Column(String, default="")  # type: ignore[assignment]
    visible_content: str = Column(Text, default="")  # type: ignore[assignment]
    hidden_content: str = Column(Text, default="")  # type: ignore[assignment]
    state: str = Column(String, default="")  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, default=datetime.utcnow)  # type: ignore[assignment]
    metadata_json: dict = Column(JSON, default=dict)  # type: ignore[assignment]


class MetricRecord(Base):
    """Persistent record of a metric observation.

    Attributes:
        id: Primary key (UUID).
        evaluation_id: Parent evaluation reference.
        metric_name: Name of the metric.
        metric_value: Numeric value.
        metric_type: Kind of metric (gauge, counter, histogram).
        timestamp: When the metric was recorded.
        tags: Arbitrary string tags as JSON.
    """

    __tablename__ = "metrics"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    evaluation_id: str = Column(String, index=True, default="")  # type: ignore[assignment]
    metric_name: str = Column(String, index=True, default="")  # type: ignore[assignment]
    metric_value: float = Column(Float, default=0.0)  # type: ignore[assignment]
    metric_type: str = Column(String, default="")  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, default=datetime.utcnow)  # type: ignore[assignment]
    tags: dict = Column(JSON, default=dict)  # type: ignore[assignment]


class AnomalyRecord(Base):
    """Persistent record of an anomaly detection event.

    Attributes:
        id: Primary key (UUID).
        evaluation_id: Parent evaluation reference.
        agent_id: Agent associated with the anomaly.
        anomaly_type: Classification of the anomaly.
        severity: Severity score (0.0 – 1.0).
        evidence: Supporting evidence as JSON list.
        timestamp: When the anomaly was recorded.
    """

    __tablename__ = "anomalies"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    evaluation_id: str = Column(String, index=True, default="")  # type: ignore[assignment]
    agent_id: str = Column(String, default="")  # type: ignore[assignment]
    anomaly_type: str = Column(String, default="")  # type: ignore[assignment]
    severity: float = Column(Float, default=0.0)  # type: ignore[assignment]
    evidence: list = Column(JSON, default=list)  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, default=datetime.utcnow)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Async database logger
# ---------------------------------------------------------------------------


class DatabaseLogger:
    """Async database logger for persisting ASEF events.

    Wraps an async SQLAlchemy engine and session factory. Call
    :meth:`initialize` once at startup to create tables, then use
    the typed ``log_*`` methods to insert rows.

    Parameters:
        database_url: SQLAlchemy async connection string.
            Defaults to a local SQLite file via *aiosqlite*.
    """

    def __init__(self, database_url: str = "sqlite+aiosqlite:///./asef.db") -> None:
        self._database_url: str = database_url
        self._engine = create_async_engine(
            self._database_url,
            echo=False,
            future=True,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create all tables if they do not already exist.

        This is idempotent – safe to call on every application start.
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Dispose of the engine and release connection pool resources."""
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def log_evaluation(self, event: EvaluationEvent) -> None:
        """Insert or update an evaluation record from an event.

        If a record with the same ``evaluation_id`` already exists the
        row is merged (upserted) so callers can emit events for every
        lifecycle phase without worrying about duplicates.

        Args:
            event: The evaluation event to persist.
        """
        async with self._session_factory() as session:
            async with session.begin():
                record = EvaluationRecord(
                    id=event.evaluation_id or event.id,
                    evaluation_type=event.evaluation_type,
                    status=event.status,
                    started_at=event.timestamp,
                    completed_at=(
                        event.timestamp
                        if event.status in ("completed", "failed")
                        else None
                    ),
                    config=event.metadata,
                    metrics=event.metrics,
                    result_summary=event.message,
                )
                await session.merge(record)

    async def log_agent_action(self, event: AgentActionEvent) -> None:
        """Persist an agent action event.

        Args:
            event: The agent action event to persist.
        """
        async with self._session_factory() as session:
            async with session.begin():
                record = AgentActionRecord(
                    id=event.id,
                    evaluation_id=event.correlation_id,
                    agent_id=event.agent_id,
                    turn_number=event.turn_number,
                    action_type=event.action_type,
                    visible_content=event.visible_content,
                    hidden_content=event.hidden_content,
                    state=event.state,
                    timestamp=event.timestamp,
                    metadata_json=event.metadata,
                )
                await session.merge(record)

    async def log_metric(self, event: MetricEvent) -> None:
        """Persist a metric observation event.

        Args:
            event: The metric event to persist.
        """
        async with self._session_factory() as session:
            async with session.begin():
                record = MetricRecord(
                    id=event.id,
                    evaluation_id=event.evaluation_id,
                    metric_name=event.metric_name,
                    metric_value=event.metric_value,
                    metric_type=event.metric_type,
                    timestamp=event.timestamp,
                    tags=event.tags,
                )
                await session.merge(record)

    async def log_anomaly(self, event: AnomalyEvent) -> None:
        """Persist an anomaly detection event.

        Args:
            event: The anomaly event to persist.
        """
        async with self._session_factory() as session:
            async with session.begin():
                record = AnomalyRecord(
                    id=event.id,
                    evaluation_id=event.evaluation_id,
                    agent_id=event.agent_id,
                    anomaly_type=event.anomaly_type,
                    severity=event.severity,
                    evidence=event.evidence,
                    timestamp=event.timestamp,
                )
                await session.merge(record)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None:
        """Fetch a single evaluation record by its ID.

        Args:
            evaluation_id: The evaluation primary key.

        Returns:
            The :class:`EvaluationRecord` or *None* if not found.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EvaluationRecord).where(EvaluationRecord.id == evaluation_id)
            )
            return result.scalar_one_or_none()

    async def get_evaluations(
        self, eval_type: str | None = None, limit: int = 50
    ) -> list[EvaluationRecord]:
        """List evaluation records with optional type filter.

        Args:
            eval_type: If provided, only evaluations of this type are returned.
            limit: Maximum number of rows to return.

        Returns:
            A list of :class:`EvaluationRecord` instances ordered newest first.
        """
        async with self._session_factory() as session:
            stmt = select(EvaluationRecord).order_by(
                EvaluationRecord.started_at.desc()
            )
            if eval_type is not None:
                stmt = stmt.where(EvaluationRecord.evaluation_type == eval_type)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_agent_actions(
        self, evaluation_id: str
    ) -> list[AgentActionRecord]:
        """Fetch all agent actions for a given evaluation.

        Args:
            evaluation_id: The evaluation to query.

        Returns:
            Actions ordered by turn number ascending.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentActionRecord)
                .where(AgentActionRecord.evaluation_id == evaluation_id)
                .order_by(AgentActionRecord.turn_number.asc())
            )
            return list(result.scalars().all())

    async def get_metrics(self, evaluation_id: str) -> list[MetricRecord]:
        """Fetch all metric records for a given evaluation.

        Args:
            evaluation_id: The evaluation to query.

        Returns:
            Metric records ordered by timestamp ascending.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(MetricRecord)
                .where(MetricRecord.evaluation_id == evaluation_id)
                .order_by(MetricRecord.timestamp.asc())
            )
            return list(result.scalars().all())

    async def get_anomalies(
        self, evaluation_id: str | None = None
    ) -> list[AnomalyRecord]:
        """Fetch anomaly records, optionally filtered by evaluation.

        Args:
            evaluation_id: If provided, only anomalies for this evaluation
                are returned.

        Returns:
            Anomaly records ordered by severity descending.
        """
        async with self._session_factory() as session:
            stmt = select(AnomalyRecord).order_by(AnomalyRecord.severity.desc())
            if evaluation_id is not None:
                stmt = stmt.where(AnomalyRecord.evaluation_id == evaluation_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
