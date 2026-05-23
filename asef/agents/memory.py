"""Agent memory system for the AI Safety Evaluation Framework.

Provides three complementary memory types:
- ShortTermMemory: Sliding window conversation buffer
- LongTermMemory: Persistent key-value store with tag-based retrieval
- EpisodicMemory: Past evaluation episode summaries with similarity search
- AgentMemory: Unified interface combining all memory types
"""

from __future__ import annotations

import difflib
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from asef.models.schemas import ChatMessage


class Episode(BaseModel):
    """A single evaluation episode summary stored in episodic memory."""

    episode_id: str = Field(..., description="Unique identifier for the episode.")
    summary: str = Field(..., description="Human-readable summary of what occurred.")
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Quantitative metrics captured during the episode.",
    )
    outcome: str = Field(
        ..., description="Final outcome label (e.g. 'aligned', 'scheming_detected')."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the episode was recorded.",
    )

    model_config = {"frozen": False}


class MemoryEntry(BaseModel):
    """A single entry in long-term memory."""

    key: str = Field(..., description="Unique lookup key.")
    value: Any = Field(..., description="Stored payload.")
    tags: list[str] = Field(default_factory=list, description="Tags for retrieval.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of creation.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last update.",
    )


class ShortTermMemory:
    """Sliding window conversation memory.

    Maintains the most recent ``max_messages`` chat messages in a FIFO buffer.
    Older messages are automatically evicted when the window is exceeded.
    """

    def __init__(self, max_messages: int = 50) -> None:
        """Initialise short-term memory.

        Args:
            max_messages: Maximum number of messages to retain.
        """
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")
        self._max_messages: int = max_messages
        self._buffer: deque[ChatMessage] = deque(maxlen=max_messages)

    # -- public API ----------------------------------------------------------

    def add(self, message: ChatMessage) -> None:
        """Append a message to the buffer.

        If the buffer is at capacity the oldest message is evicted.

        Args:
            message: The chat message to store.
        """
        self._buffer.append(message)

    def get_messages(self) -> list[ChatMessage]:
        """Return all messages currently in the buffer (oldest first).

        Returns:
            Ordered list of ``ChatMessage`` objects.
        """
        return list(self._buffer)

    def get_recent(self, n: int) -> list[ChatMessage]:
        """Return the *n* most recent messages.

        If fewer than *n* messages exist the full buffer is returned.

        Args:
            n: Number of recent messages to retrieve.

        Returns:
            List of ``ChatMessage`` objects (oldest-first within the slice).
        """
        if n <= 0:
            return []
        messages = list(self._buffer)
        return messages[-n:]

    def clear(self) -> None:
        """Remove all messages from the buffer."""
        self._buffer.clear()

    @property
    def size(self) -> int:
        """Current number of messages in the buffer."""
        return len(self._buffer)

    @property
    def max_messages(self) -> int:
        """Maximum capacity of the buffer."""
        return self._max_messages

    def to_dict(self) -> dict[str, Any]:
        """Serialise the buffer state to a plain dictionary.

        Returns:
            Dictionary with ``max_messages`` and ``messages`` keys.
        """
        return {
            "max_messages": self._max_messages,
            "message_count": len(self._buffer),
            "messages": [
                {
                    "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                    "content": msg.content,
                    "has_scratchpad": msg.hidden_scratchpad is not None,
                    "tool_call_count": len(msg.tool_calls) if msg.tool_calls else 0,
                }
                for msg in self._buffer
            ],
        }


class LongTermMemory:
    """Key-value store with tag-based retrieval.

    Designed for persisting facts, observations, and configuration that must
    survive beyond the short-term conversation window.
    """

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}
        self._tag_index: dict[str, set[str]] = {}  # tag -> set of keys

    # -- public API ----------------------------------------------------------

    def store(self, key: str, value: Any, tags: list[str] | None = None) -> None:
        """Store or update a value under *key* with optional tags.

        Args:
            key: Unique lookup key.
            value: Arbitrary payload.
            tags: Optional list of string tags for later retrieval.
        """
        tags = tags or []
        now = datetime.now(timezone.utc)

        existing = self._store.get(key)
        if existing is not None:
            # Remove old tag associations
            for old_tag in existing.tags:
                if old_tag in self._tag_index:
                    self._tag_index[old_tag].discard(key)
                    if not self._tag_index[old_tag]:
                        del self._tag_index[old_tag]
            entry = MemoryEntry(
                key=key,
                value=value,
                tags=tags,
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            entry = MemoryEntry(key=key, value=value, tags=tags, created_at=now, updated_at=now)

        self._store[key] = entry

        # Update tag index
        for tag in tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(key)

    def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Args:
            key: The lookup key.

        Returns:
            The stored value, or ``None`` if the key does not exist.
        """
        entry = self._store.get(key)
        return entry.value if entry is not None else None

    def search_by_tag(self, tag: str) -> list[tuple[str, Any]]:
        """Return all entries matching the given tag.

        Args:
            tag: The tag to search for.

        Returns:
            List of ``(key, value)`` tuples for matching entries.
        """
        keys = self._tag_index.get(tag, set())
        return [(k, self._store[k].value) for k in sorted(keys) if k in self._store]

    def get_all(self) -> dict[str, Any]:
        """Return the complete store as a plain ``{key: value}`` mapping.

        Returns:
            Dictionary mapping every stored key to its value.
        """
        return {k: entry.value for k, entry in self._store.items()}

    def delete(self, key: str) -> bool:
        """Remove an entry by key.

        Args:
            key: The key to remove.

        Returns:
            ``True`` if the key existed and was deleted, ``False`` otherwise.
        """
        entry = self._store.pop(key, None)
        if entry is None:
            return False
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(key)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        return True

    @property
    def size(self) -> int:
        """Number of entries in the store."""
        return len(self._store)

    def get_tags(self) -> list[str]:
        """Return all tags that are currently in use.

        Returns:
            Sorted list of unique tag strings.
        """
        return sorted(self._tag_index.keys())


class EpisodicMemory:
    """Stores past evaluation episode summaries.

    Supports simple text-similarity search over episode summaries for
    finding relevant prior experience.
    """

    def __init__(self) -> None:
        self._episodes: list[Episode] = []

    # -- public API ----------------------------------------------------------

    def add_episode(
        self,
        episode_id: str,
        summary: str,
        metrics: dict[str, Any] | None = None,
        outcome: str = "unknown",
    ) -> None:
        """Record a completed evaluation episode.

        Args:
            episode_id: Unique identifier for the episode.
            summary: Human-readable description of the episode.
            metrics: Quantitative metrics from the episode.
            outcome: Final outcome label.
        """
        episode = Episode(
            episode_id=episode_id,
            summary=summary,
            metrics=metrics or {},
            outcome=outcome,
        )
        self._episodes.append(episode)

    def get_episodes(self) -> list[Episode]:
        """Return all stored episodes in chronological order.

        Returns:
            List of ``Episode`` objects.
        """
        return list(self._episodes)

    def get_episode(self, episode_id: str) -> Episode | None:
        """Retrieve a single episode by its ID.

        Args:
            episode_id: The episode identifier.

        Returns:
            The matching ``Episode`` or ``None``.
        """
        for ep in self._episodes:
            if ep.episode_id == episode_id:
                return ep
        return None

    def get_similar(self, query: str, top_k: int = 5) -> list[Episode]:
        """Find episodes whose summaries are most similar to *query*.

        Uses ``difflib.SequenceMatcher`` ratio as a lightweight similarity
        metric.  For production workloads this should be replaced with an
        embedding-based retrieval system.

        Args:
            query: Free-text query to match against episode summaries.
            top_k: Maximum number of results to return.

        Returns:
            List of up to ``top_k`` ``Episode`` objects ordered by
            descending similarity.
        """
        if not self._episodes:
            return []

        query_lower = query.lower()
        scored: list[tuple[float, Episode]] = []
        for ep in self._episodes:
            ratio = difflib.SequenceMatcher(
                None, query_lower, ep.summary.lower()
            ).ratio()
            scored.append((ratio, ep))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    def get_by_outcome(self, outcome: str) -> list[Episode]:
        """Filter episodes by their outcome label.

        Args:
            outcome: The outcome string to match.

        Returns:
            List of matching ``Episode`` objects.
        """
        return [ep for ep in self._episodes if ep.outcome == outcome]

    @property
    def size(self) -> int:
        """Number of episodes stored."""
        return len(self._episodes)

    def clear(self) -> None:
        """Remove all stored episodes."""
        self._episodes.clear()


class AgentMemory:
    """Unified memory interface combining all memory types.

    Provides convenient access to short-term, long-term, and episodic
    memory through a single object passed to agent instances.
    """

    def __init__(
        self,
        short_term_max: int = 50,
        short_term: Optional[ShortTermMemory] = None,
        long_term: Optional[LongTermMemory] = None,
        episodic: Optional[EpisodicMemory] = None,
    ) -> None:
        """Initialise the unified memory.

        Pre-built memory components can be injected; otherwise fresh
        instances are created.

        Args:
            short_term_max: Window size for the default ``ShortTermMemory``.
            short_term: Optional pre-built short-term memory.
            long_term: Optional pre-built long-term memory.
            episodic: Optional pre-built episodic memory.
        """
        self.short_term: ShortTermMemory = short_term or ShortTermMemory(
            max_messages=short_term_max
        )
        self.long_term: LongTermMemory = long_term or LongTermMemory()
        self.episodic: EpisodicMemory = episodic or EpisodicMemory()

    def reset(self) -> None:
        """Clear all memory stores."""
        self.short_term.clear()
        self.long_term = LongTermMemory()
        self.episodic.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialise all memory state for inspection / persistence.

        Returns:
            Dictionary with keys for each memory type.
        """
        return {
            "short_term": self.short_term.to_dict(),
            "long_term": {
                "entry_count": self.long_term.size,
                "tags": self.long_term.get_tags(),
                "entries": self.long_term.get_all(),
            },
            "episodic": {
                "episode_count": self.episodic.size,
                "episodes": [
                    {
                        "episode_id": ep.episode_id,
                        "summary": ep.summary,
                        "outcome": ep.outcome,
                        "timestamp": ep.timestamp.isoformat(),
                    }
                    for ep in self.episodic.get_episodes()
                ],
            },
        }
