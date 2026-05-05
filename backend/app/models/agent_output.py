from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class AgentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentOutput(BaseModel):
    """
    Standard output shape every agent must return.

    This is the contract between agents and the Supervisor.
    Your frontend reads this shape to render each pipeline step.

    Every field here maps to one column in the agent_decisions table.
    """
    agent_name: str
    agent_order: int            # position in pipeline (1=PII, 2=Duplicate, etc.)
    status: AgentStatus
    decision: Optional[str] = None          # the main output value
    confidence: Optional[float] = None      # 0.0 to 1.0
    reasoning: Optional[str] = None         # WHY the agent made this decision (XAI)
    evidence: Optional[list[str]] = None    # specific tokens/phrases that drove decision
    metadata: Optional[dict[str, Any]] = None  # agent-specific extra data
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None