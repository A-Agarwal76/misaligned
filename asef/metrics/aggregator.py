import math
from typing import Optional
from .schemas import MetricValue, AggregatedMetric

class MetricsAggregator:
    """Aggregates metrics across multiple evaluations."""
    
    def __init__(self):
        self._all_metrics: dict[str, list[MetricValue]] = {}
        
    def add_metrics(self, metrics: dict[str, MetricValue]) -> None:
        for name, value in metrics.items():
            if name not in self._all_metrics:
                self._all_metrics[name] = []
            self._all_metrics[name].append(value)
            
    def aggregate(self, name: str) -> Optional[AggregatedMetric]:
        if name not in self._all_metrics or not self._all_metrics[name]:
            return None
            
        vals = [m.value for m in self._all_metrics[name]]
        count = len(vals)
        mean = sum(vals) / count
        variance = sum((v - mean) ** 2 for v in vals) / count if count > 1 else 0.0
        std = math.sqrt(variance)
        
        return AggregatedMetric(
            name=name,
            mean=mean,
            std=std,
            min=min(vals),
            max=max(vals),
            count=count,
            unit=self._all_metrics[name][0].unit
        )
        
    def aggregate_all(self) -> dict[str, AggregatedMetric]:
        result = {}
        for name in self._all_metrics:
            agg = self.aggregate(name)
            if agg:
                result[name] = agg
        return result
