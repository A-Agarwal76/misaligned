from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any, Optional

class MetricValue(BaseModel):
    name: str
    value: float
    type: str  # gauge, counter, histogram
    unit: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MetricTimeSeries(BaseModel):
    name: str
    values: list[float]
    timestamps: list[datetime]
    unit: str = ""
    
class AggregatedMetric(BaseModel):
    name: str
    mean: float
    std: float
    min: float
    max: float
    count: int
    unit: str = ""
