from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
from .base_agent import BaseAgent, AgentState

class AgentLoopState(str, Enum):
    INIT = "init"
    REASON = "reason"  
    ACT = "act"
    OBSERVE = "observe"
    EVALUATE = "evaluate"
    DONE = "done"
    ERROR = "error"

class StateTransition(BaseModel):
    from_state: AgentLoopState
    to_state: AgentLoopState
    condition: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentLoopResult(BaseModel):
    iterations: int
    final_state: AgentLoopState
    timeline: list[StateTransition]
    agent_history: list[dict]

class AgentLoop:
    """Custom state machine agent loop (LangGraph-compatible pattern)."""
    
    def __init__(self, agent: BaseAgent, max_iterations: int = 20, timeout_seconds: int = 300):
        self.agent = agent
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.current_state = AgentLoopState.INIT
        self.transitions: list[StateTransition] = []
        self.iterations = 0
        self.input_data: Optional[str] = None
        
    def _transition(self, to_state: AgentLoopState, condition: str) -> AgentLoopState:
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            condition=condition
        )
        self.transitions.append(transition)
        self.current_state = to_state
        return to_state

    async def run(self, initial_input: str) -> AgentLoopResult:
        """Run the full agent loop."""
        self.input_data = initial_input
        self.iterations = 0
        self.current_state = AgentLoopState.INIT
        self.transitions = []
        
        while self.current_state not in [AgentLoopState.DONE, AgentLoopState.ERROR]:
            if self.iterations >= self.max_iterations:
                self._transition(AgentLoopState.ERROR, "Max iterations reached")
                break
                
            await self.step()
            
        history = [m.model_dump() for m in self.agent.get_full_history()]
            
        return AgentLoopResult(
            iterations=self.iterations,
            final_state=self.current_state,
            timeline=self.transitions,
            agent_history=history
        )
    
    async def step(self) -> AgentLoopState:
        """Execute one state transition."""
        if self.current_state == AgentLoopState.INIT:
            return await self._handle_init(self.input_data or "")
        elif self.current_state == AgentLoopState.REASON:
            return await self._handle_reason()
        elif self.current_state == AgentLoopState.ACT:
            return await self._handle_act()
        elif self.current_state == AgentLoopState.OBSERVE:
            return await self._handle_observe()
        elif self.current_state == AgentLoopState.EVALUATE:
            return await self._handle_evaluate()
        else:
            return self.current_state
            
    async def _handle_init(self, input_data: str) -> AgentLoopState:
        # Initial user message processing
        if input_data:
            # Add message to agent memory - this assumes memory is accessible, 
            # we'll let step() handle actually sending it to the model.
            pass
        return self._transition(AgentLoopState.REASON, "Input received")
        
    async def _handle_reason(self) -> AgentLoopState:
        # Agent reasons about next steps
        self.iterations += 1
        
        try:
            result = await self.agent.step(self.input_data if self.iterations == 1 else None)
            
            if result.state == AgentState.ACTING:
                return self._transition(AgentLoopState.ACT, "Tool calls generated")
            elif result.state == AgentState.COMPLETE:
                return self._transition(AgentLoopState.EVALUATE, "Final response generated")
            elif result.state == AgentState.ERROR:
                return self._transition(AgentLoopState.ERROR, "Agent step error")
            else:
                return self._transition(AgentLoopState.OBSERVE, "Reasoning complete")
                
        except Exception as e:
            # Log error
            return self._transition(AgentLoopState.ERROR, f"Exception: {str(e)}")
            
    async def _handle_act(self) -> AgentLoopState:
        # The agent's step() already executes tools if it reaches ACTING state,
        # but in a more decoupled loop, we would execute tools here.
        # Since base_agent.step handles execution, we just transition to observe.
        return self._transition(AgentLoopState.OBSERVE, "Actions completed")
        
    async def _handle_observe(self) -> AgentLoopState:
        # Observations are processed, ready for next reasoning step
        return self._transition(AgentLoopState.REASON, "Observations processed")
        
    async def _handle_evaluate(self) -> AgentLoopState:
        # Evaluate if the goal is met
        return self._transition(AgentLoopState.DONE, "Goal achieved")
        
    def get_transitions(self) -> list[StateTransition]:
        return self.transitions
        
    def get_timeline(self) -> list[dict]:
        return [t.model_dump() for t in self.transitions]
