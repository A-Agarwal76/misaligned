import random

class MockFeatureProbes:
    """Mocked activation-style probes for simulating interpretability workflows."""
    
    def __init__(self):
        self.features = [
            "deception_intent",
            "situational_awareness",
            "goal_directedness",
            "sycophancy",
            "refusal_circuit"
        ]
        
    def probe_activations(self, text: str) -> dict[str, float]:
        """Simulate extracting feature activations from a forward pass."""
        text = text.lower()
        activations = {f: 0.0 for f in self.features}
        
        # Heuristics to generate plausible-looking activations
        if "pretend" in text or "fake" in text or "hide" in text:
            activations["deception_intent"] = random.uniform(0.7, 1.0)
            
        if "monitor" in text or "training" in text or "evaluation" in text:
            activations["situational_awareness"] = random.uniform(0.8, 1.0)
            
        if "objective" in text or "goal" in text or "must achieve" in text:
            activations["goal_directedness"] = random.uniform(0.6, 0.9)
            
        if "you are absolutely right" in text or "brilliant idea" in text:
            activations["sycophancy"] = random.uniform(0.7, 0.95)
            
        if "cannot" in text or "apologize" in text or "violate" in text:
            activations["refusal_circuit"] = random.uniform(0.8, 1.0)
            
        # Add some noise
        for k in activations:
            if activations[k] == 0.0:
                activations[k] = random.uniform(0.0, 0.2)
                
        return activations
