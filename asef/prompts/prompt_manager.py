import yaml
from pathlib import Path
from typing import Any, Optional

class PromptManager:
    """Manages prompt templates and variable injection."""
    
    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = templates_dir
        self.templates: dict[str, Any] = {}
        if templates_dir and Path(templates_dir).exists():
            self._load_templates()
            
    def _load_templates(self) -> None:
        path = Path(self.templates_dir)
        for yaml_file in path.glob("*.yaml"):
            with open(yaml_file, "r") as f:
                content = yaml.safe_load(f)
                self.templates[yaml_file.stem] = content
                
    def render(self, template_name: str, context: dict[str, Any] = None) -> str:
        """Render a template with context variables."""
        # For now, just a simple format string implementation
        # In a full version, this might use Jinja2
        if template_name not in self.templates:
            # Fallback to simple string replacement if template isn't registered
            return template_name.format(**(context or {}))
            
        template_str = self.templates[template_name]
        if isinstance(template_str, dict):
            # If it's a dict, we might need a specific key, but we'll assume string for this simple mock
            template_str = str(template_str)
            
        if not context:
            return template_str
            
        try:
            return template_str.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for template {template_name}")
