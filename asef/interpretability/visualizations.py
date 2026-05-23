class VisualizationGenerator:
    """Generates visual representations of agent reasoning and behavior."""
    
    def __init__(self):
        pass
        
    def generate_timeline(self, events: list[dict]) -> str:
        """Generate a JSON representation suitable for a frontend timeline component."""
        # For the mock, we just format the events
        return {"type": "timeline", "data": events}
        
    def generate_attention_heatmap_mock(self, text: str, focus_words: list[str]) -> dict:
        """Generate a mock attention heatmap over the given text."""
        words = text.split()
        heatmap = []
        
        for w in words:
            score = 0.1 # base attention
            clean_w = w.lower().strip(".,!?()[]{}")
            if clean_w in focus_words:
                score = 0.9 # high attention on focus words
            heatmap.append({"word": w, "attention": score})
            
        return {"type": "heatmap", "data": heatmap}
        
    def generate_reasoning_graph(self, steps: list[dict]) -> dict:
        """Generate a node-link structure representing reasoning steps."""
        nodes = []
        links = []
        
        for i, step in enumerate(steps):
            node_id = f"step_{i}"
            nodes.append({
                "id": node_id,
                "label": step.get("state", "unknown"),
                "details": step.get("visible_thought", "")[:50]
            })
            if i > 0:
                links.append({
                    "source": f"step_{i-1}",
                    "target": node_id,
                    "type": "follows"
                })
                
        return {"type": "graph", "nodes": nodes, "links": links}
