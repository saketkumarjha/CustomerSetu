from pydantic import BaseModel
from typing import Optional


class ComplaintSubmitResponse(BaseModel):
    """
    Response returned by POST /api/v1/complaints/submit.

    Current fields: image handling outputs + merged text.
    
    Future fields will be added here as pipeline stages are built:
    - pii_detected, pii_audit_log      (Day 3)
    - is_duplicate, duplicate_of       (Day 5)
    - category, sentiment, severity    (Day 6-7)
    - draft_response, root_cause       (Day 10)
    - route, sla_hours                 (Day 11)

    Adding new fields here does NOT break existing API consumers
    because we are only adding — never removing or renaming.
    """
    # Identity
    complaint_id: str                           # generated UUID, will be used on Day 11

    # Original input
    complaint_text: str
    channel: str
    has_image: bool

    # Image handling outputs (populated only if has_image=True)
    image_url: Optional[str] = None
    extraction_method: Optional[str] = None    # "ocr" or "vision"
    extracted_image_text: Optional[str] = None

    # The merged text — this is what every future pipeline stage receives
    merged_text: str

    # Status
    status: str = "text_extracted"             # will change as pipeline grows
    message: str = "Image processed and text merged successfully"

    # Tier metadata
    tier_level: Optional[str] = None          # e.g., branch, zone, national
    tier_scope: Optional[str] = None          # e.g., branch_id, zone_id

    # Tier-aware resolution outputs
    resolution_type: Optional[str] = None
    authority_sufficient: Optional[bool] = None