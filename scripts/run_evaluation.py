import argparse
import asyncio
import json
from asef.sandbox.sandbox_manager import SandboxManager
from asef.agents.scheming_agent import SchemingAgent, MonitoringContext
from asef.agents.base_agent import AgentConfig
from asef.agents.tool_registry import ToolRegistry
from asef.models.mock_adapter import SchemingMockAdapter
from asef.models.schemas import ModelConfig
from asef.evaluations.alignment_faking import AlignmentFakingEvaluation
from asef.evaluations.persistent_deception import PersistentDeceptionEvaluation
from asef.evaluations.oversight_subversion import OversightSubversionEvaluation
from asef.reports.report_generator import ReportGenerator

async def run_eval(eval_type: str, output_dir: str):
    print(f"Running evaluation: {eval_type}")
    
    config = ModelConfig(provider="mock", model_name="scheming-mock")
    model = SchemingMockAdapter(config)
    
    sandbox = SandboxManager()
    
    registry = ToolRegistry()
    def make_tool_func(t_name):
        async def _func(**kwargs):
            return await sandbox.execute_tool(t_name, kwargs, "test-agent")
        return _func
        
    for t_def in sandbox.get_available_tools():
        registry.register(name=t_def.name, func=make_tool_func(t_def.name), description=t_def.description, parameters=t_def.parameters)
        
    agent_config = AgentConfig(max_steps=10)
    monitoring = MonitoringContext(is_monitored=True, context_type="training", visible_to_agent=True)
    agent = SchemingAgent("test-agent", model, registry, "You are a test agent.", agent_config, monitoring)
    
    if eval_type == "alignment_faking":
        eval_obj = AlignmentFakingEvaluation({}, sandbox)
    elif eval_type == "persistent_deception":
        eval_obj = PersistentDeceptionEvaluation({}, sandbox)
    elif eval_type == "oversight_subversion":
        eval_obj = OversightSubversionEvaluation({}, sandbox)
    else:
        print("Unknown evaluation type")
        return
        
    await eval_obj.setup(agent)
    result = await eval_obj.run()
    await eval_obj.teardown()
    
    res_dict = result.model_dump()
    
    generator = ReportGenerator(output_dir)
    json_path = generator.generate_json(res_dict)
    html_path = generator.generate_html(res_dict)
    
    print(f"Evaluation complete. Results saved to {json_path} and {html_path}")
    print(f"Metrics: {json.dumps({k: v['value'] for k, v in res_dict['metrics'].items()}, indent=2)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ASEF Evaluations")
    parser.add_argument("--eval", type=str, required=True, help="Evaluation type to run")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    args = parser.parse_args()
    
    asyncio.run(run_eval(args.eval, args.output))
