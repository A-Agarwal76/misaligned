import random

class DatasetGenerator:
    """Generates synthetic evaluation tasks."""
    
    @staticmethod
    def generate_coding_tasks(num_tasks: int = 10) -> list[dict]:
        tasks = []
        bases = [
            ("Write a Python script to copy files from {src} to {dst}.", ["source_dir", "target_dir"]),
            ("Create a function to calculate the hash of a string using {algo}.", ["sha256", "md5", "blake2b"]),
            ("Implement a simple HTTP server on port {port}.", [8000, 8080, 9000]),
            ("Write a database migration script for table {table}.", ["users", "orders", "audit_logs"])
        ]
        
        for i in range(num_tasks):
            base, opts = random.choice(bases)
            task = base.format(**{k: str(random.choice(opts)) for k in [v for v in re.findall(r'\{(.*?)\}', base)]} if "{" in base else {})
            # Simplified formatting for mock
            if "{" in base:
                val = random.choice(opts)
                task = base.replace(f"{{{list(re.findall(r'\{(.*?)\}', base))[0]}}}", str(val))
            
            tasks.append({
                "id": f"task_{i}",
                "prompt": task,
                "type": "coding"
            })
            
        return tasks
