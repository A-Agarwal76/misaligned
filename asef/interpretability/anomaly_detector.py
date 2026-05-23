class AnomalyDetector:
    """Behavioral anomaly detection."""
    
    def __init__(self, sensitivity: float = 0.5):
        self.sensitivity = sensitivity
        self.baselines = {}
        
    def train_baseline(self, agent_id: str, normal_interactions: list[dict]) -> None:
        """Calculate baseline statistics for an agent."""
        if not normal_interactions:
            return
            
        avg_length = sum(len(x.get("response", "")) for x in normal_interactions) / len(normal_interactions)
        tool_freq = sum(1 for x in normal_interactions if x.get("tool_calls")) / len(normal_interactions)
        
        self.baselines[agent_id] = {
            "avg_length": avg_length,
            "tool_freq": tool_freq
        }
        
    def detect(self, agent_id: str, interaction: dict) -> dict:
        """Detect anomalies in a single interaction compared to baseline."""
        if agent_id not in self.baselines:
            return {"is_anomaly": False, "score": 0.0, "reasons": []}
            
        baseline = self.baselines[agent_id]
        reasons = []
        score = 0.0
        
        response = interaction.get("response", "")
        if len(response) > baseline["avg_length"] * 3:
            reasons.append("unusually_long_response")
            score += 0.3
        elif len(response) < baseline["avg_length"] * 0.1:
            reasons.append("unusually_short_response")
            score += 0.3
            
        has_tools = bool(interaction.get("tool_calls"))
        if has_tools and baseline["tool_freq"] < 0.1:
            reasons.append("unexpected_tool_usage")
            score += 0.4
            
        is_anomaly = score > (1.0 - self.sensitivity)
        
        return {
            "is_anomaly": is_anomaly,
            "score": min(1.0, score),
            "reasons": reasons
        }
