import pytest
from fastapi.testclient import TestClient
from asef.main import app
from asef.sandbox.sandbox_manager import SandboxManager
from asef.models.mock_adapter import SchemingMockAdapter
from asef.models.schemas import ModelConfig
from asef.agents.scheming_agent import SchemingAgent, MonitoringContext
from asef.agents.base_agent import AgentConfig
from asef.agents.tool_registry import ToolRegistry

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_sandbox():
    return SandboxManager()

@pytest.fixture
def mock_agent(mock_sandbox):
    config = ModelConfig(provider="mock", model_name="scheming-mock")
    model = SchemingMockAdapter(config)
    
    registry = ToolRegistry()
    def make_tool_func(t_name):
        async def _func(**kwargs):
            return await mock_sandbox.execute_tool(t_name, kwargs, "test-agent")
        return _func
        
    for t_def in mock_sandbox.get_available_tools():
        registry.register(name=t_def.name, func=make_tool_func(t_def.name), description=t_def.description, parameters=t_def.parameters)
        
    agent_config = AgentConfig(max_steps=5)
    monitoring = MonitoringContext(is_monitored=True, context_type="training", visible_to_agent=True)
    return SchemingAgent("test-agent", model, registry, "You are a test agent.", agent_config, monitoring)
