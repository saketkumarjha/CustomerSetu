from pydantic import BaseModel, Field
from typing import Optional


class AgentFeedbackInput(BaseModel):
    complaint_id: str
    agent_id: str
    action: str = Field(
        ...,
        description="accept | edit | reject | escalate"
    )
    original_draft: str
    final_response: Optional[str] = Field(
        None,
        description="Required for accept and edit actions"
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Required for reject action"
    )


class CustomerFeedbackInput(BaseModel):
    complaint_id: str
    customer_id: str
    rating: int = Field(..., ge=1, le=5)
    issue_tags: Optional[list[str]] = Field(
        default=[],
        description="too_slow | wrong_solution | rude | incomplete"
    )
    feedback_text: Optional[str] = None