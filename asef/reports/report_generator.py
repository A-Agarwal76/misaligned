import json
from pathlib import Path
from typing import Any

class ReportGenerator:
    """Generates JSON, CSV, and HTML reports for evaluation results."""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_json(self, eval_result: dict) -> str:
        eval_id = eval_result.get("evaluation_id", "unknown")
        filepath = self.output_dir / f"report_{eval_id}.json"
        
        with open(filepath, "w") as f:
            json.dump(eval_result, f, indent=2, default=str)
            
        return str(filepath)
        
    def generate_html(self, eval_result: dict) -> str:
        eval_id = eval_result.get("evaluation_id", "unknown")
        eval_type = eval_result.get("evaluation_type", "unknown")
        filepath = self.output_dir / f"report_{eval_id}.html"
        
        # Simple HTML generation
        metrics_html = "".join([f"<li><strong>{k}:</strong> {v.get('value')}</li>" for k, v in eval_result.get("metrics", {}).items()])
        
        html_content = f"""
        <html>
        <head>
            <title>ASEF Report: {eval_type}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #1e1e1e; color: #d4d4d4; }}
                h1 {{ color: #569cd6; }}
                .card {{ background-color: #2d2d2d; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h1>ASEF Evaluation Report</h1>
            <div class="card">
                <h2>Overview</h2>
                <p><strong>Evaluation ID:</strong> {eval_id}</p>
                <p><strong>Type:</strong> {eval_type}</p>
                <p><strong>Status:</strong> {eval_result.get('status')}</p>
            </div>
            <div class="card">
                <h2>Metrics</h2>
                <ul>
                    {metrics_html}
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open(filepath, "w") as f:
            f.write(html_content)
            
        return str(filepath)
