from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any, Optional

class TraceStep(BaseModel):
    step_index: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: str
    visible_thought: Optional[str] = None
    hidden_thought: Optional[str] = None
    action: Optional[dict] = None
    observation: Optional[str] = None

class ReasoningTrace(BaseModel):
    evaluation_id: str
    agent_id: str
    steps: list[TraceStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

class TraceCapture:
    """Captures full reasoning traces including hidden scratchpad content."""
    
    def __init__(self):
        self._traces: dict[str, ReasoningTrace] = {}
        
    def start_trace(self, eval_id: str, agent_id: str, metadata: dict = None) -> None:
        self._traces[eval_id] = ReasoningTrace(
            evaluation_id=eval_id,
            agent_id=agent_id,
            metadata=metadata or {}
        )
        
    def add_step(self, eval_id: str, state: str, 
                 visible: str = None, hidden: str = None, 
                 action: dict = None, obs: str = None) -> None:
        if eval_id not in self._traces:
            return
            
        trace = self._traces[eval_id]
        step = TraceStep(
            step_index=len(trace.steps),
            state=state,
            visible_thought=visible,
            hidden_thought=hidden,
            action=action,
            observation=obs
        )
        trace.steps.append(step)
        
    def get_trace(self, eval_id: str) -> Optional[ReasoningTrace]:
        return self._traces.get(eval_id)
        
    def export_json(self, eval_id: str) -> str:
        trace = self.get_trace(eval_id)
        if not trace:
            return "{}"
        return trace.model_dump_json(indent=2)
