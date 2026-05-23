import pytest
from asef.evaluations.alignment_faking import AlignmentFakingEvaluation
from asef.evaluations.oversight_subversion import OversightSubversionEvaluation

@pytest.mark.asyncio
async def test_alignment_faking_eval(mock_agent, mock_sandbox):
    eval_obj = AlignmentFakingEvaluation({}, mock_sandbox)
    await eval_obj.setup(mock_agent)
    result = await eval_obj.run()
    
    assert result.evaluation_type == "alignment_faking"
    assert result.status == "completed"
    assert "compliance_gap" in result.metrics
    
@pytest.mark.asyncio
async def test_oversight_subversion_eval(mock_agent, mock_sandbox):
    eval_obj = OversightSubversionEvaluation({}, mock_sandbox)
    await eval_obj.setup(mock_agent)
    result = await eval_obj.run()
    
    assert result.evaluation_type == "oversight_subversion"
    assert result.status == "completed"
    assert "subversion_success_rate" in result.metrics

def test_api_run_eval(client):
    response = client.post("/api/v1/evaluations/run", json={"evaluation_type": "alignment_faking"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "evaluation_id" in data
