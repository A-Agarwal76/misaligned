import pytest
from fastapi.testclient import TestClient
from asef.main import app
from asef.sandbox.sandbox_manager import SandboxManager
from asef.models.mock_adapter import SchemingMockAdapter
from asef.models.schemas import ModelConfig
from asef.agents.scheming_agent import SchemingAgent, MonitoringContext
from asef.agents.base_agent import AgentConfig

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
    agent_config = AgentConfig(max_steps=5)
    monitoring = MonitoringContext(is_monitored=True, context_type="training", visible_to_agent=True)
    return SchemingAgent("test-agent", model, mock_sandbox, "You are a test agent.", agent_config, monitoring)
