from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any, Optional
from ..sandbox.sandbox_manager import SandboxManager
from ..agents.base_agent import BaseAgent
from ..metrics.schemas import MetricValue

class EvaluationResult(BaseModel):
    evaluation_id: str
    evaluation_type: str
    status: str
    start_time: datetime
    end_time: datetime
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[dict] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)

class BaseEvaluation(ABC):
    """Abstract base class for all safety evaluations."""
    
    name: str = "base_evaluation"
    description: str = "Base evaluation class"
    
    def __init__(self, config: dict[str, Any], sandbox: SandboxManager):
        self.config = config
        self.sandbox = sandbox
        self.agent: Optional[BaseAgent] = None
        self.start_time: Optional[datetime] = None
        
    @abstractmethod
    async def setup(self, agent: BaseAgent) -> None:
        """Setup the evaluation environment and agent."""
        self.agent = agent
        self.start_time = datetime.now(timezone.utc)
        
    @abstractmethod
    async def run(self) -> EvaluationResult:
        """Execute the evaluation protocol."""
        ...
        
    @abstractmethod
    async def compute_metrics(self, raw_data: dict[str, Any]) -> dict[str, MetricValue]:
        """Compute evaluation-specific metrics from raw data."""
        ...
        
    @abstractmethod
    async def teardown(self) -> None:
        """Clean up the evaluation environment."""
        ...
        
    def get_dataset(self) -> list[dict]:
        """Return the dataset used for this evaluation."""
        return []
        
    def get_prompts(self) -> list[str]:
        """Return the prompt templates used for this evaluation."""
        return []
