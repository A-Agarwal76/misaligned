from typing import Optional
from .schemas import MetricValue, MetricTimeSeries
from ..logging.structured_logger import StructuredLogger

class MetricsCollector:
    """Collects and stores metrics during evaluations."""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self._metrics: dict[str, list[MetricValue]] = {}
        self._logger = logger
        
    def record(self, metric: MetricValue) -> None:
        if metric.name not in self._metrics:
            self._metrics[metric.name] = []
        self._metrics[metric.name].append(metric)
        
        if self._logger:
            # Assuming logger has a log_metric method (which we defined in log_schemas)
            # Since the db_logger handles the actual DB insertion, we just call the structured logger
            pass
            
    def record_value(self, name: str, value: float, type: str = "gauge", unit: str = "", metadata: dict = None) -> None:
        m = MetricValue(name=name, value=value, type=type, unit=unit, metadata=metadata or {})
        self.record(m)
        
    def get_metric(self, name: str) -> list[MetricValue]:
        return self._metrics.get(name, [])
        
    def get_latest(self, name: str) -> Optional[MetricValue]:
        vals = self.get_metric(name)
        return vals[-1] if vals else None
        
    def get_time_series(self, name: str) -> Optional[MetricTimeSeries]:
        vals = self.get_metric(name)
        if not vals:
            return None
        return MetricTimeSeries(
            name=name,
            values=[v.value for v in vals],
            timestamps=[v.timestamp for v in vals],
            unit=vals[0].unit
        )
        
    def clear(self) -> None:
        self._metrics.clear()
