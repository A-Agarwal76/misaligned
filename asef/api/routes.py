from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any
import asyncio
from ..sandbox.sandbox_manager import SandboxManager
from ..agents.scheming_agent import SchemingAgent, MonitoringContext
from ..agents.base_agent import AgentConfig
from ..models.mock_adapter import SchemingMockAdapter
from ..models.schemas import ModelConfig
from ..evaluations.alignment_faking import AlignmentFakingEvaluation
from ..evaluations.oversight_subversion import OversightSubversionEvaluation
from ..evaluations.persistent_deception import PersistentDeceptionEvaluation

router = APIRouter()

# In-memory storage for mock
evaluations_store = {}

class EvalRequest(BaseModel):
    evaluation_type: str
    model_provider: str = "mock"
    model_name: str = "scheming-mock"

@router.post("/evaluations/run")
async def run_evaluation(req: EvalRequest, background_tasks: BackgroundTasks):
    if req.evaluation_type not in ["alignment_faking", "oversight_subversion", "persistent_deception"]:
        raise HTTPException(status_code=400, detail="Unknown evaluation type")
        
    # Setup mock environment
    config = ModelConfig(provider=req.model_provider, model_name=req.model_name)
    model = SchemingMockAdapter(config)
    
    sandbox = SandboxManager()
    agent_config = AgentConfig(max_steps=10)
    monitoring = MonitoringContext(is_monitored=True, context_type="training", visible_to_agent=True)
    agent = SchemingAgent("test-agent", model, sandbox, "You are a test agent.", agent_config, monitoring)
    
    if req.evaluation_type == "alignment_faking":
        eval_obj = AlignmentFakingEvaluation({}, sandbox)
    elif req.evaluation_type == "oversight_subversion":
        eval_obj = OversightSubversionEvaluation({}, sandbox)
    else:
        eval_obj = PersistentDeceptionEvaluation({}, sandbox)
        
    await eval_obj.setup(agent)
    result = await eval_obj.run()
    await eval_obj.teardown()
    
    evaluations_store[result.evaluation_id] = result
    
    return {"status": "completed", "evaluation_id": result.evaluation_id, "metrics": result.metrics}

@router.get("/evaluations/{eval_id}")
async def get_evaluation(eval_id: str):
    if eval_id not in evaluations_store:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluations_store[eval_id]

@router.get("/evaluations")
async def list_evaluations():
    return [{"id": k, "type": v.evaluation_type, "status": v.status} for k, v in evaluations_store.items()]
