"""
Admin Knowledge Base Management API

Exposes all CRUD + analytics + bulk import + queue endpoints
that the React/Vite admin dashboard consumes.

Prefix (registered in api/v1/__init__.py): /admin/kb
Auth: X-API-Key header applied globally via the existing middleware.

Endpoints
---------
GET  /admin/kb/reference                  — categories, tier labels, etc.
GET  /admin/kb/metrics                    — dashboard KPIs
GET  /admin/kb/entries                    — paginated list with filters
GET  /admin/kb/entries/{id}              — single entry with resolution_text
POST /admin/kb/entries                    — create (generates embedding)
PUT  /admin/kb/entries/{id}              — update (regenerates embedding if text changed)
DELETE /admin/kb/entries/{id}            — delete

GET  /admin/kb/analytics                  — usage / coverage / quality data

GET  /admin/kb/templates/csv             — download CSV import template
GET  /admin/kb/templates/json            — download JSON import template
POST /admin/kb/bulk-validate             — validate file without saving
POST /admin/kb/bulk-import               — import CSV/JSON (generates embeddings)

GET  /admin/kb/queue                     — list pending auto-generated entries
POST /admin/kb/queue/{id}/approve        — approve + add to KB (optional edit body)
POST /admin/kb/queue/{id}/reject         — reject single entry
POST /admin/kb/queue/bulk-reject         — reject all pending
"""

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Body, File, HTTPException, Query, Path, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, BeforeValidator, field_validator

from app.core.config import get_settings
from app.db.supabase_client import get_supabase

router = APIRouter()
settings = get_settings()


def _int_not_bool(v):
    """Reject bool and non-integer floats; coerce whole-number floats → int."""
    if isinstance(v, bool):
        raise ValueError("Expected an integer, not a boolean")
    if isinstance(v, float):
        if not v.is_integer():
            raise ValueError("Expected an integer value, not a fractional float")
        return int(v)
    return v

# ── OpenAI client (lazy singleton) ────────────────────────────────────────────

_oai_client = None


def _oai():
    global _oai_client
    if _oai_client is None:
        from openai import OpenAI
        _oai_client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
            max_retries=1,
        )
    return _oai_client


def _gen_embedding(text: str) -> list:
    resp = _oai().embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        dimensions=settings.openai_embedding_dimension,
    )
    return resp.data[0].embedding

# ── Constants ─────────────────────────────────────────────────────────────────

TIER_LABELS = {
    0: "General (All Branches)",
    1: "Branch",
    2: "Zone",
    3: "Region",
    4: "Head Office",
    5: "Ombudsman",
}

TIER_SCOPE_FORMATS = {
    0: None,
    1: "BRANCH:{code}",
    2: "ZONE:{name}",
    3: "REGION:{name}",
    4: "HEAD_OFFICE",
    5: "OMBUDSMAN",
}

CATEGORIES = [
    "UPI", "ATM", "Debit Card", "Credit Card", "Home Loan",
    "Personal Loan", "Business Loan", "Savings Account", "Current Account",
    "Internet Banking", "Mobile App", "KYC / Account", "Cheque",
    "Branch Service", "Forex", "Locker", "Escalation", "Fraud",
    "General Banking", "Other",
]

REGIONS = ["Western", "Eastern", "Northern", "Southern", "Central"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_tier(t) -> int:
    if isinstance(t, int):
        return t
    mapping = {
        "general": 0, "branch": 1, "zone": 2,
        "regional": 3, "region": 3, "national": 4,
        "head_office": 4, "ombudsman": 5,
    }
    return mapping.get(str(t).lower(), 0)


def _insert_kb(db, row: dict) -> dict:
    """Insert row, silently retrying without issue_type if that column is missing."""
    try:
        result = db.table("knowledge_base").insert(row).execute()
    except Exception as e:
        if "issue_type" in str(e):
            row.pop("issue_type", None)
            result = db.table("knowledge_base").insert(row).execute()
        else:
            raise
    return result


def _update_kb(db, entry_id: str, row: dict):
    try:
        db.table("knowledge_base").update(row).eq("id", entry_id).execute()
    except Exception as e:
        if "issue_type" in str(e):
            row.pop("issue_type", None)
            db.table("knowledge_base").update(row).eq("id", entry_id).execute()
        else:
            raise

# ── Pydantic models ───────────────────────────────────────────────────────────

class KBEntryCreate(BaseModel):
    model_config = {"strict": True}
    tier_level: Annotated[int, BeforeValidator(_int_not_bool), Field(ge=0, le=5, description="0=General … 5=Ombudsman")]
    tier_scope: Optional[str] = Field(None, description="BRANCH:xxx / ZONE:xxx / REGION:xxx / HEAD_OFFICE / OMBUDSMAN")
    category: str
    issue_type: Optional[str] = None
    resolution_text: str = Field(..., min_length=50)
    quality_score: float = Field(0.85, ge=0.0, le=1.0)
    verified: bool = False

    @field_validator("resolution_text", mode="before")
    @classmethod
    def strip_null_bytes(cls, v):
        if isinstance(v, str):
            return v.replace("\x00", "")
        return v


class KBEntryUpdate(BaseModel):
    model_config = {"strict": True}
    tier_level: Annotated[int, BeforeValidator(_int_not_bool), Field(ge=0, le=5)]
    tier_scope: Optional[str] = None
    category: str
    issue_type: Optional[str] = None
    resolution_text: str = Field(..., min_length=50)
    quality_score: float = Field(..., ge=0.0, le=1.0)
    verified: bool

    @field_validator("resolution_text", mode="before")
    @classmethod
    def strip_null_bytes(cls, v):
        if isinstance(v, str):
            return v.replace("\x00", "")
        return v


class KBEntrySummary(BaseModel):
    id: str
    tier_level: int
    tier_scope: Optional[str] = None
    category: str
    issue_type: Optional[str] = None
    quality_score: float
    verified: bool
    usage_count: int = 0
    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class KBEntryDetail(KBEntrySummary):
    resolution_text: str


class PaginatedEntries(BaseModel):
    entries: List[KBEntrySummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class TierStat(BaseModel):
    tier_level: int
    label: str
    count: int


class CoverageGap(BaseModel):
    category: str
    count: int
    needed: int


class RecentEntry(BaseModel):
    id: str
    tier_level: int
    category: str
    issue_type: Optional[str] = None
    quality_score: float
    verified: bool
    source: Optional[str] = None
    created_at: Optional[str] = None


class DashboardMetrics(BaseModel):
    total: int
    verified: int
    pending: int
    avg_quality: float
    tier_distribution: List[TierStat]
    coverage_gaps: List[CoverageGap]
    recent_additions: List[RecentEntry]


class AnalyticsData(BaseModel):
    top_entries_by_usage: List[dict]
    category_usage: List[dict]
    tier_coverage_matrix: List[dict]
    category_gaps: List[dict]
    quality_distribution: List[dict]
    tier_quality: List[dict]


class QueueEntry(BaseModel):
    id: int
    complaint_id: Optional[str] = None
    resolution_text: Optional[str] = None
    scheduled_for: Optional[str] = None
    added_to_kb: bool = False
    created_at: Optional[str] = None
    # Enriched fields (populated after migration 010)
    tier_level: int = 0
    tier_scope: Optional[str] = None
    category: Optional[str] = None
    issue_type: Optional[str] = None
    confidence_score: float = 0.0
    recommended_quality_score: float = 0.0
    quality_signals_json: Optional[dict] = None
    agent_action: Optional[str] = None
    customer_feedback_score: Optional[float] = None
    resolution_type: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApproveQueueRequest(BaseModel):
    # All optional — falls back to queue row values if not provided
    category: Optional[str] = None
    issue_type: Optional[str] = None
    resolution_text: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    tier_level: Optional[int] = Field(None, ge=0, le=5)
    tier_scope: Optional[str] = None
    verified: bool = True


class RejectQueueRequest(BaseModel):
    reason: str = "Rejected by admin"


class BulkApproveRequest(BaseModel):
    model_config = {"strict": True}
    min_quality_score: float = Field(0.95, ge=0.0, le=1.0)
    tier_level: Optional[Annotated[int, BeforeValidator(_int_not_bool), Field(ge=0, le=5)]] = None
    category: Optional[str] = None


class BulkValidateResult(BaseModel):
    total: int
    valid: int
    errors: int
    rows: List[dict]


class BulkImportResult(BaseModel):
    total_rows: int
    successful: int
    failed: int
    errors: List[dict]

# ── Row serializers ───────────────────────────────────────────────────────────

def _to_summary(r: dict) -> KBEntrySummary:
    return KBEntrySummary(
        id=r["id"],
        tier_level=_normalize_tier(r.get("tier_level", 0)),
        tier_scope=r.get("tier_scope"),
        category=r.get("category", ""),
        issue_type=r.get("issue_type"),
        quality_score=r.get("quality_score", 0.5),
        verified=bool(r.get("verified", False)),
        usage_count=r.get("usage_count") or 0,
        source=r.get("source"),
        created_at=r.get("created_at"),
        updated_at=r.get("updated_at"),
    )


def _to_detail(r: dict) -> KBEntryDetail:
    return KBEntryDetail(
        **_to_summary(r).model_dump(),
        resolution_text=r.get("resolution_text", ""),
    )

# ── Reference data ────────────────────────────────────────────────────────────

@router.get("/reference", summary="Return lookup data (categories, tier labels, scope formats) for the frontend")
async def get_reference():
    return {
        "categories": CATEGORIES,
        "tier_labels": TIER_LABELS,
        "tier_scope_formats": TIER_SCOPE_FORMATS,
        "regions": REGIONS,
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimensions": settings.openai_embedding_dimension,
    }

# ── Dashboard metrics ─────────────────────────────────────────────────────────

@router.get("/metrics", response_model=DashboardMetrics, summary="Dashboard KPI cards, tier distribution, coverage gaps, recent additions",
            responses={500: {"description": "Database error"}})
async def get_dashboard_metrics():
    db = get_supabase()
    try:
        rows = db.table("knowledge_base").select(
            "id, tier_level, category, issue_type, quality_score, verified, source, created_at"
        ).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    total = len(rows)
    if total == 0:
        return DashboardMetrics(
            total=0, verified=0, pending=0, avg_quality=0.0,
            tier_distribution=[], coverage_gaps=[], recent_additions=[],
        )

    verified_count = sum(1 for r in rows if r.get("verified"))
    avg_quality = round(sum(r.get("quality_score") or 0 for r in rows) / total, 3)

    tier_counts: dict[int, int] = {}
    for r in rows:
        t = _normalize_tier(r.get("tier_level", 0))
        tier_counts[t] = tier_counts.get(t, 0) + 1

    tier_distribution = [
        TierStat(tier_level=t, label=TIER_LABELS.get(t, f"Tier {t}"), count=c)
        for t, c in sorted(tier_counts.items())
    ]

    cat_counts: dict[str, int] = {}
    for r in rows:
        c = r.get("category") or "Other"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    coverage_gaps = [
        CoverageGap(category=c, count=cat_counts.get(c, 0), needed=max(0, 3 - cat_counts.get(c, 0)))
        for c in CATEGORIES
        if cat_counts.get(c, 0) < 3
    ]

    recent = sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)[:10]
    recent_additions = [
        RecentEntry(
            id=r["id"],
            tier_level=_normalize_tier(r.get("tier_level", 0)),
            category=r.get("category") or "",
            issue_type=r.get("issue_type"),
            quality_score=r.get("quality_score") or 0.0,
            verified=bool(r.get("verified", False)),
            source=r.get("source"),
            created_at=r.get("created_at"),
        )
        for r in recent
    ]

    return DashboardMetrics(
        total=total,
        verified=verified_count,
        pending=total - verified_count,
        avg_quality=avg_quality,
        tier_distribution=tier_distribution,
        coverage_gaps=coverage_gaps,
        recent_additions=recent_additions,
    )

# ── Entries CRUD ──────────────────────────────────────────────────────────────

@router.get("/entries", response_model=PaginatedEntries, summary="List KB entries with filtering, sorting, and pagination",
            responses={500: {"description": "Database error"}})
async def list_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tier_level: Optional[str] = Query(None, description="Filter by tier level 0-5 (null/empty = all tiers)"),
    category: Optional[str] = None,
    verified: Optional[str] = Query(None, description="Filter by verified status: true, false, or omit"),
    source: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search in issue_type and category"),
    sort_by: str = Query("created_at", pattern="^(created_at|quality_score|usage_count|tier_level)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    # Parse verified string — tolerate "null", "", None gracefully
    verified_bool: Optional[bool] = None
    if verified is not None and verified.lower() not in ("", "null", "none"):
        verified_bool = verified.lower() in ("true", "1", "yes")

    # Parse tier_level string — tolerate "null", "" sent by Schemathesis / browsers gracefully
    tier_level_int: Optional[int] = None
    if tier_level is not None and tier_level.lower() not in ("", "null", "none"):
        try:
            tier_level_int = int(tier_level)
        except ValueError:
            pass  # invalid value → treat as no filter

    db = get_supabase()
    try:
        q = db.table("knowledge_base").select(
            "id, tier_level, tier_scope, category, issue_type, "
            "quality_score, verified, usage_count, source, created_at, updated_at"
        )
        if tier_level_int is not None:
            q = q.eq("tier_level", tier_level_int)
        if category:
            q = q.eq("category", category)
        if verified_bool is not None:
            q = q.eq("verified", verified_bool)
        if source:
            q = q.eq("source", source)
        q = q.order(sort_by, desc=(sort_order == "desc"))
        rows = q.execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # In-memory search (avoids needing full-text index for admin use)
    if search:
        s = search.lower()
        rows = [
            r for r in rows
            if s in (r.get("issue_type") or "").lower()
            or s in (r.get("category") or "").lower()
        ]

    total = len(rows)
    offset = (page - 1) * page_size
    page_rows = rows[offset: offset + page_size]

    return PaginatedEntries(
        entries=[_to_summary(r) for r in page_rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),
    )


@router.get("/entries/{entry_id}", response_model=KBEntryDetail, summary="Get a single KB entry including resolution_text",
            responses={404: {"description": "Entry not found"}, 500: {"description": "Database error"}})
async def get_entry(entry_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", description="KB entry UUID")):
    db = get_supabase()
    try:
        rows = db.table("knowledge_base").select(
            "id, tier_level, tier_scope, category, issue_type, resolution_text, "
            "quality_score, verified, usage_count, source, created_at, updated_at"
        ).eq("id", entry_id).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    if not rows:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _to_detail(rows[0])


@router.post("/entries", response_model=KBEntryDetail, status_code=201, summary="Create a new KB entry (auto-generates embedding)",
             responses={422: {"description": "tier_scope required when tier_level > 0"}, 500: {"description": "Embedding generation or database insert failed"}})
async def create_entry(payload: KBEntryCreate):
    if payload.tier_level > 0 and not payload.tier_scope:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "tier_scope"], "msg": "tier_scope is required when tier_level > 0", "type": "value_error.missing"}],
        )

    embedding = await asyncio.to_thread(_gen_embedding, payload.resolution_text)

    row = {
        "tier_level": payload.tier_level,
        "tier_scope": payload.tier_scope,
        "category": payload.category,
        "resolution_text": payload.resolution_text,
        "quality_score": payload.quality_score,
        "verified": payload.verified,
        "embedding": embedding,
        "source": "admin",
    }
    if payload.issue_type:
        row["issue_type"] = payload.issue_type

    db = get_supabase()
    try:
        result = _insert_kb(db, row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

    if not result.data:
        raise HTTPException(status_code=500, detail="Insert returned no data")

    saved = result.data[0]
    saved.setdefault("resolution_text", payload.resolution_text)
    saved.setdefault("issue_type", payload.issue_type)
    return _to_detail(saved)


@router.put("/entries/{entry_id}", response_model=KBEntryDetail, summary="Update a KB entry (regenerates embedding only when resolution_text changes)",
            responses={404: {"description": "Entry not found"}, 500: {"description": "Database or embedding error"}})
async def update_entry(entry_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", description="KB entry UUID"), payload: KBEntryUpdate = Body(...)):
    if payload.tier_level > 0 and not payload.tier_scope:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "tier_scope"], "msg": "tier_scope is required when tier_level > 0", "type": "value_error.missing"}],
        )

    db = get_supabase()
    try:
        existing = db.table("knowledge_base").select(
            "resolution_text"
        ).eq("id", entry_id).execute().data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")

    text_changed = existing[0].get("resolution_text", "") != payload.resolution_text

    row: dict = {
        "tier_level": payload.tier_level,
        "tier_scope": payload.tier_scope,
        "category": payload.category,
        "issue_type": payload.issue_type,
        "resolution_text": payload.resolution_text,
        "quality_score": payload.quality_score,
        "verified": payload.verified,
    }
    if text_changed:
        row["embedding"] = await asyncio.to_thread(_gen_embedding, payload.resolution_text)

    try:
        _update_kb(db, entry_id, row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB update failed: {e}")

    # Re-fetch to get DB-generated timestamps
    updated = db.table("knowledge_base").select(
        "id, tier_level, tier_scope, category, issue_type, resolution_text, "
        "quality_score, verified, usage_count, source, created_at, updated_at"
    ).eq("id", entry_id).execute().data or []
    if not updated:
        raise HTTPException(status_code=500, detail="Could not fetch updated row")
    return _to_detail(updated[0])


@router.delete("/entries/{entry_id}", summary="Delete a KB entry",
               responses={404: {"description": "Entry not found"}})
async def delete_entry(entry_id: str):
    db = get_supabase()
    try:
        existing = db.table("knowledge_base").select("id").eq("id", entry_id).execute().data
        if not existing:
            raise HTTPException(status_code=404, detail="Entry not found")
        db.table("knowledge_base").delete().eq("id", entry_id).execute()
    except HTTPException:
        raise
    except Exception:
        # Non-UUID strings cause a Postgres type error — treat as 404 (no such entry)
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": f"Entry {entry_id} deleted successfully"}

# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=AnalyticsData, summary="Usage stats, coverage heatmap, quality distribution",
            responses={500: {"description": "Database error"}})
async def get_analytics():
    db = get_supabase()
    try:
        rows = db.table("knowledge_base").select(
            "id, tier_level, category, issue_type, quality_score, verified, usage_count, created_at"
        ).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    for r in rows:
        r["tier_level"] = _normalize_tier(r.get("tier_level", 0))
        r["usage_count"] = r.get("usage_count") or 0
        r["quality_score"] = r.get("quality_score") or 0.5

    # Top 20 entries by usage_count
    top = sorted(rows, key=lambda r: r["usage_count"], reverse=True)[:20]
    top_entries_by_usage = [
        {
            "id": r["id"],
            "label": r.get("issue_type") or r.get("category") or f"#{r['id']}",
            "usage": r["usage_count"],
            "tier_level": r["tier_level"],
            "category": r.get("category"),
        }
        for r in top
    ]

    # Category usage totals (sum usage_count, fallback to 1 per entry for charts)
    cat_usage: dict[str, int] = {}
    for r in rows:
        c = r.get("category") or "Other"
        cat_usage[c] = cat_usage.get(c, 0) + max(r["usage_count"], 1)
    category_usage = [
        {"category": c, "count": v}
        for c, v in sorted(cat_usage.items(), key=lambda x: -x[1])
    ]

    # Tier × category coverage matrix (entry count per cell)
    all_cats = sorted({r.get("category") or "Other" for r in rows})
    all_tiers = sorted({r["tier_level"] for r in rows})
    matrix: dict[str, dict[int, int]] = {c: {t: 0 for t in all_tiers} for c in all_cats}
    for r in rows:
        c = r.get("category") or "Other"
        t = r["tier_level"]
        if c in matrix:
            matrix[c][t] = matrix[c].get(t, 0) + 1
    tier_coverage_matrix = [
        {"category": c, "tier": t, "tier_label": TIER_LABELS.get(t, str(t)), "entries": matrix[c].get(t, 0)}
        for c in all_cats
        for t in all_tiers
    ]

    # Categories with fewer than 3 entries
    cat_counts = {c: sum(1 for r in rows if r.get("category") == c) for c in CATEGORIES}
    category_gaps = [
        {"category": c, "count": cat_counts.get(c, 0), "needed": max(0, 3 - cat_counts.get(c, 0))}
        for c in CATEGORIES
        if cat_counts.get(c, 0) < 3
    ]

    # Quality score distribution in 0.1-wide buckets
    buckets: dict[str, int] = {}
    for r in rows:
        q = r.get("quality_score") or 0.0
        b = f"{int(q * 10) / 10:.1f}–{min(int(q * 10) / 10 + 0.1, 1.0):.1f}"
        buckets[b] = buckets.get(b, 0) + 1
    quality_distribution = [{"range": b, "count": v} for b, v in sorted(buckets.items())]

    # Average quality and entry count per tier
    tier_q_map: dict[int, list] = {}
    for r in rows:
        tier_q_map.setdefault(r["tier_level"], []).append(r["quality_score"])
    tier_quality = [
        {
            "tier_level": t,
            "label": TIER_LABELS.get(t, f"Tier {t}"),
            "avg_quality": round(sum(qs) / len(qs), 3),
            "count": len(qs),
        }
        for t, qs in sorted(tier_q_map.items())
    ]

    return AnalyticsData(
        top_entries_by_usage=top_entries_by_usage,
        category_usage=category_usage,
        tier_coverage_matrix=tier_coverage_matrix,
        category_gaps=category_gaps,
        quality_distribution=quality_distribution,
        tier_quality=tier_quality,
    )

# ── Import templates ──────────────────────────────────────────────────────────

_CSV_TEMPLATE = (
    "tier_level,tier_scope,category,issue_type,resolution_text,quality_score,verified\n"
    '0,,UPI,Transaction Failed,"Dear Customer, we have investigated your UPI failed '
    "transaction. As per RBI TAT guidelines, the reversal will be processed within "
    '5 working days from the date of the failed transaction. We sincerely apologize.",0.90,true\n'
    '1,BRANCH:BR_MH_001,ATM,ATM Cash Not Dispensed,"Dear Customer, we apologize for the '
    "ATM inconvenience at our Fort Branch. After verification, a provisional credit has been "
    "applied to your account. Please visit the branch with your transaction receipt for final "
    'resolution within 5 working days.",0.85,false\n'
)

_JSON_TEMPLATE = json.dumps([
    {
        "tier_level": 0,
        "tier_scope": None,
        "category": "UPI",
        "issue_type": "Transaction Failed",
        "resolution_text": (
            "Dear Customer, we have investigated your UPI failed transaction. "
            "As per RBI TAT guidelines, the reversal will be processed within "
            "5 working days from the date of the failed transaction. "
            "We sincerely apologize for the inconvenience caused."
        ),
        "quality_score": 0.9,
        "verified": True,
    },
], indent=2)


@router.get(
    "/templates/csv",
    summary="Download CSV import template",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV import template file"}},
)
async def csv_template():
    return StreamingResponse(
        iter([_CSV_TEMPLATE]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kb_import_template.csv"},
    )


@router.get(
    "/templates/json",
    summary="Download JSON import template",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/json": {}}, "description": "JSON import template file"}},
)
async def json_template():
    return StreamingResponse(
        iter([_JSON_TEMPLATE]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kb_import_template.json"},
    )

# ── Bulk import helpers ───────────────────────────────────────────────────────

_REQUIRED = {"tier_level", "category", "resolution_text"}

# Accepted aliases mapped to canonical field names
_FIELD_ALIASES = {"resolution": "resolution_text"}


def _normalize_row(row: dict) -> dict:
    """Return a copy of row with alias field names mapped to canonical names."""
    normalized = dict(row)
    for alias, canonical in _FIELD_ALIASES.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized.pop(alias)
    return normalized


def _parse_upload(content: bytes, filename: str) -> list[dict]:
    if filename.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Support envelope formats: { "records": [...] }, { "data": [...] }, etc.
            for key in ("records", "data", "entries", "items", "knowledge_base"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    if filename.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        return list(reader)
    raise ValueError(f"Unsupported file type: {filename}")


def _validate_row(row: dict) -> list[str]:
    missing = _REQUIRED - set(row.keys())
    if missing:
        return [f"Missing required columns: {', '.join(missing)}"]
    errs = []
    try:
        tl = int(row["tier_level"])
        if tl not in range(6):
            errs.append("tier_level must be 0–5")
        if tl > 0 and not row.get("tier_scope"):
            errs.append("tier_scope required when tier_level > 0")
    except (ValueError, TypeError):
        errs.append(f"Invalid tier_level value: {row.get('tier_level')!r}")
    if len(row.get("resolution_text", "")) < 20:
        errs.append("resolution_text is too short (minimum 20 characters)")
    q = row.get("quality_score")
    if q is not None:
        try:
            if not 0.0 <= float(q) <= 1.0:
                errs.append("quality_score must be 0.0–1.0")
        except (ValueError, TypeError):
            errs.append(f"Invalid quality_score value: {q!r}")
    return errs


# ── Bulk validate (dry-run) ───────────────────────────────────────────────────

_BULK_FILE_DESCRIPTION = (
    "CSV or JSON file upload (multipart/form-data). "
    "Accepted extensions: .csv, .json. "
    "Max size: 10 MB. "
    "The field must be a real file upload — sending a plain string will be rejected."
)
_BULK_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/bulk-validate", response_model=BulkValidateResult, summary="Validate import file and return per-row results without saving",
             responses={400: {"description": "Wrong file type, file too large, or parse error"}})
async def bulk_validate(file: Optional[UploadFile] = File(None, description=_BULK_FILE_DESCRIPTION)):
    if file is None:
        return BulkValidateResult(total=0, valid=0, errors=0, rows=[])
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file has no filename. Send a real .csv or .json file via multipart/form-data.",
        )
    if not (file.filename.endswith(".csv") or file.filename.endswith(".json")):
        raise HTTPException(status_code=400, detail="Only .csv and .json files are supported")
    content = await file.read()
    if len(content) > _BULK_MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is 10 MB.")
    try:
        rows = _parse_upload(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File parse error: {e}")

    results = []
    for i, raw_row in enumerate(rows):
        row = _normalize_row(raw_row)
        errs = _validate_row(row)
        results.append({
            "row": i + 1,
            "status": "error" if errs else "valid",
            "errors": errs,
            "preview": {
                "tier_level": row.get("tier_level"),
                "category": row.get("category"),
                "issue_type": row.get("issue_type"),
                "resolution_preview": (row.get("resolution_text") or "")[:120],
            },
        })

    return BulkValidateResult(
        total=len(rows),
        valid=sum(1 for r in results if r["status"] == "valid"),
        errors=sum(1 for r in results if r["status"] == "error"),
        rows=results,
    )


# ── Bulk import ───────────────────────────────────────────────────────────────

@router.post("/bulk-import", response_model=BulkImportResult, summary="Import KB entries from CSV or JSON (generates embeddings for each row)",
             responses={400: {"description": "Wrong file type, file too large, or parse error"}})
async def bulk_import(file: Optional[UploadFile] = File(None, description=_BULK_FILE_DESCRIPTION)):
    if file is None:
        return BulkImportResult(total_rows=0, successful=0, failed=0, errors=[])
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file has no filename. Send a real .csv or .json file via multipart/form-data.",
        )
    if not (file.filename.endswith(".csv") or file.filename.endswith(".json")):
        raise HTTPException(status_code=400, detail="Only .csv and .json files are supported")
    content = await file.read()
    if len(content) > _BULK_MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is 10 MB.")
    try:
        rows = _parse_upload(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File parse error: {e}")

    db = get_supabase()
    successful, failed = 0, 0
    errors: list[dict] = []

    for i, raw_row in enumerate(rows):
        row = _normalize_row(raw_row)
        row_errs = _validate_row(row)
        if row_errs:
            failed += 1
            errors.append({"row": i + 1, "errors": row_errs})
            continue
        try:
            text = row["resolution_text"]
            embedding = await asyncio.to_thread(_gen_embedding, text)
            entry: dict = {
                "tier_level": int(row["tier_level"]),
                "tier_scope": row.get("tier_scope") or None,
                "category": row["category"],
                "resolution_text": text,
                "quality_score": float(row.get("quality_score") or 0.85),
                "verified": str(row.get("verified", "false")).lower() == "true",
                "embedding": embedding,
                "source": "bulk_import",
            }
            if row.get("issue_type"):
                entry["issue_type"] = row["issue_type"]
            _insert_kb(db, entry)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({"row": i + 1, "error": str(e)})

    return BulkImportResult(
        total_rows=len(rows),
        successful=successful,
        failed=failed,
        errors=errors,
    )

# ── Auto-generated queue ──────────────────────────────────────────────────────

@router.get("/queue", response_model=List[QueueEntry], summary="List auto-generated KB entries awaiting review",
            responses={500: {"description": "Database error or kb_enrichment_queue table missing"}})
async def list_queue(
    processed: Optional[str] = Query(None, description="Pending (false) or processed (true) entries", pattern="^(true|false|null)$"),
    min_quality: Optional[str] = Query(None, description="Filter by minimum quality score 0.0–1.0 (null/empty = all)"),
    tier_level: Optional[str] = Query(None, description="Filter by tier level 0-5 (null/empty = all tiers)"),
    category: Optional[str] = None,
    sort_by: str = Query("recommended_quality_score", pattern="^(recommended_quality_score|created_at)$"),
):
    # Parse tier_level string — tolerate "null", "" gracefully
    tier_level_int: Optional[int] = None
    if tier_level is not None and tier_level.lower() not in ("", "null", "none"):
        try:
            tier_level_int = int(tier_level)
        except ValueError:
            pass

    # Parse min_quality string — tolerate "null", "" gracefully
    min_quality_float: Optional[float] = None
    if min_quality is not None and min_quality.lower() not in ("", "null", "none"):
        try:
            min_quality_float = float(min_quality)
        except ValueError:
            pass

    processed_bool = processed.lower() == "true" if processed is not None else False

    db = get_supabase()
    _ENRICHED_COLS = (
        "id, complaint_id, resolution_text, scheduled_for, added_to_kb, created_at, "
        "tier_level, tier_scope, category, issue_type, confidence_score, "
        "recommended_quality_score, quality_signals_json, agent_action, "
        "customer_feedback_score, resolution_type, rejection_reason"
    )
    # Minimal columns guaranteed to exist on any version of this table.
    _BASE_COLS = "id, complaint_id, resolution_text, scheduled_for, added_to_kb"

    rows: list = []
    for cols, order_col in [(_ENRICHED_COLS, sort_by), (_BASE_COLS, "id")]:
        try:
            q = db.table("kb_enrichment_queue").select(cols).eq("processed", processed_bool)
            if tier_level_int is not None:
                q = q.eq("tier_level", tier_level_int)
            if category:
                q = q.eq("category", category)
            rows = q.order(order_col, desc=True).execute().data or []
            break  # succeeded — stop trying fallbacks
        except Exception:
            continue
    else:
        # Both queries failed — table likely missing entirely
        raise HTTPException(
            status_code=500,
            detail="kb_enrichment_queue table not found or schema too old. Run the migration first.",
        )

    if min_quality_float is not None:
        rows = [r for r in rows if (r.get("recommended_quality_score") or 0.0) >= min_quality_float]

    return [
        QueueEntry(
            id=r["id"],
            complaint_id=r.get("complaint_id"),
            resolution_text=r.get("resolution_text"),
            scheduled_for=r.get("scheduled_for"),
            added_to_kb=bool(r.get("added_to_kb", False)),
            created_at=r.get("created_at"),
            tier_level=int(r.get("tier_level") or 0),
            tier_scope=r.get("tier_scope"),
            category=r.get("category"),
            issue_type=r.get("issue_type"),
            confidence_score=float(r.get("confidence_score") or 0.0),
            recommended_quality_score=float(r.get("recommended_quality_score") or 0.0),
            quality_signals_json=r.get("quality_signals_json"),
            agent_action=r.get("agent_action"),
            customer_feedback_score=r.get("customer_feedback_score"),
            resolution_type=r.get("resolution_type"),
            rejection_reason=r.get("rejection_reason"),
        )
        for r in rows
    ]


@router.post("/queue/{queue_id}/approve", summary="Approve a queued entry and insert it into knowledge_base",
             responses={404: {"description": "Queue entry not found"}, 500: {"description": "Database or embedding error"}})
async def approve_queue_entry(queue_id: int, payload: ApproveQueueRequest):
    db = get_supabase()
    try:
        q_rows = (
            db.table("kb_enrichment_queue")
            .select(
                "id, complaint_id, resolution_text, tier_level, tier_scope, "
                "category, issue_type, recommended_quality_score"
            )
            .eq("id", queue_id)
            .execute()
            .data or []
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    if not q_rows:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    q    = q_rows[0]
    text = payload.resolution_text or q.get("resolution_text") or ""
    if not text:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "resolution_text"], "msg": "resolution_text is empty — provide it in the request body", "type": "value_error.missing"}],
        )

    # Resolve values: request body overrides queue row values
    tier_level    = payload.tier_level    if payload.tier_level is not None else int(q.get("tier_level") or 0)
    tier_scope    = payload.tier_scope    or q.get("tier_scope")
    category      = payload.category      or q.get("category") or "General Banking"
    issue_type    = payload.issue_type    or q.get("issue_type")
    quality_score = payload.quality_score if payload.quality_score is not None else float(q.get("recommended_quality_score") or 0.85)

    embedding = await asyncio.to_thread(_gen_embedding, text)

    entry: dict = {
        "resolution_text": text,
        "category":        category,
        "tier_level":      tier_level,
        "tier_scope":      tier_scope,
        "quality_score":   quality_score,
        "verified":        payload.verified,
        "embedding":       embedding,
        "source":          "auto_enrichment",
    }
    if q.get("complaint_id"):
        entry["complaint_id"]        = q["complaint_id"]
        entry["source_complaint_id"] = q["complaint_id"]
    if issue_type:
        entry["issue_type"] = issue_type

    try:
        result = _insert_kb(db, entry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KB insert failed: {e}")

    new_id = result.data[0]["id"] if result.data else None
    db.table("kb_enrichment_queue").update({
        "processed":    True,
        "added_to_kb":  True,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", queue_id).execute()

    return {
        "message":     "Entry approved and added to knowledge base",
        "kb_entry_id": new_id,
        "tier_level":  tier_level,
        "category":    category,
        "verified":    payload.verified,
    }


@router.post("/queue/{queue_id}/reject", summary="Reject a single queued entry",
             responses={404: {"description": "Queue entry not found"}, 500: {"description": "Database error"}})
async def reject_queue_entry(queue_id: int, payload: RejectQueueRequest = RejectQueueRequest()):
    db = get_supabase()
    try:
        existing = db.table("kb_enrichment_queue").select("id").eq("id", queue_id).execute().data
        if not existing:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        db.table("kb_enrichment_queue").update({
            "processed":        True,
            "added_to_kb":      False,
            "rejection_reason": payload.reason,
            "processed_at":     datetime.now(timezone.utc).isoformat(),
        }).eq("id", queue_id).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": f"Queue entry {queue_id} rejected", "reason": payload.reason}


@router.post("/queue/bulk-approve", summary="Bulk approve queue entries meeting quality / tier criteria",
             responses={500: {"description": "Database error querying queue"}})
async def bulk_approve_queue(payload: BulkApproveRequest):
    """
    Approves all pending entries where recommended_quality_score >= min_quality_score.
    Optionally filters by tier_level and category.
    """
    db = get_supabase()
    try:
        q = (
            db.table("kb_enrichment_queue")
            .select(
                "id, complaint_id, resolution_text, tier_level, tier_scope, "
                "category, issue_type, recommended_quality_score"
            )
            .eq("processed", False)
            .gte("recommended_quality_score", payload.min_quality_score)
        )
        if payload.tier_level is not None:
            q = q.eq("tier_level", payload.tier_level)
        if payload.category:
            q = q.eq("category", payload.category)
        entries = q.execute().data or []
    except Exception:
        # recommended_quality_score column may not exist yet (pre-migration).
        # Fall back to fetching without it and filtering in Python.
        try:
            q2 = (
                db.table("kb_enrichment_queue")
                .select("id, complaint_id, resolution_text, tier_level, tier_scope, category, issue_type")
                .eq("processed", False)
            )
            if payload.tier_level is not None:
                q2 = q2.eq("tier_level", payload.tier_level)
            if payload.category:
                q2 = q2.eq("category", payload.category)
            raw = q2.execute().data or []
            # Column absent → all quality scores are effectively 0.0
            entries = [
                {**r, "recommended_quality_score": 0.0}
                for r in raw
                if 0.0 >= payload.min_quality_score
            ]
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"DB error: {e2}")

    approved = 0
    failed   = 0
    errors:  list = []

    for entry in entries:
        try:
            text = entry.get("resolution_text", "")
            if not text or len(text) < 50:
                failed += 1
                errors.append({"id": entry["id"], "error": "resolution_text too short"})
                continue

            embedding = await asyncio.to_thread(_gen_embedding, text)
            tier_level = int(entry.get("tier_level") or 0)
            tier_scope = entry.get("tier_scope")
            category   = entry.get("category") or "General Banking"
            issue_type = entry.get("issue_type")
            quality    = float(entry.get("recommended_quality_score") or 0.85)

            kb_row: dict = {
                "resolution_text":    text,
                "category":           category,
                "tier_level":         tier_level,
                "tier_scope":         tier_scope,
                "quality_score":      quality,
                "verified":           True,
                "embedding":          embedding,
                "source":             "auto_enrichment",
            }
            if entry.get("complaint_id"):
                kb_row["complaint_id"]        = entry["complaint_id"]
                kb_row["source_complaint_id"] = entry["complaint_id"]
            if issue_type:
                kb_row["issue_type"] = issue_type

            _insert_kb(db, kb_row)

            db.table("kb_enrichment_queue").update({
                "processed":    True,
                "added_to_kb":  True,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", entry["id"]).execute()

            approved += 1

        except Exception as exc:
            failed += 1
            errors.append({"id": entry["id"], "error": str(exc)})

    return {
        "approved": approved,
        "failed":   failed,
        "total":    len(entries),
        "errors":   errors[:10],  # cap to avoid huge responses
    }


@router.post("/queue/bulk-reject", summary="Reject all currently pending auto-generated entries",
             responses={500: {"description": "Database error"}})
async def bulk_reject_queue(payload: RejectQueueRequest):
    db = get_supabase()
    try:
        pending = (
            db.table("kb_enrichment_queue")
            .select("id")
            .eq("processed", False)
            .execute()
            .data or []
        )
        count = len(pending)
        if count:
            db.table("kb_enrichment_queue").update({
                "processed":        True,
                "added_to_kb":      False,
                "rejection_reason": payload.reason,
                "processed_at":     datetime.now(timezone.utc).isoformat(),
            }).eq("processed", False).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": f"Rejected {count} pending entries", "count": count}


# ── Scheduled job triggers (admin-invoked) ────────────────────────────────────

@router.post("/jobs/process-queue", summary="Manually trigger queue processing (auto-approve high-quality entries)")
async def trigger_process_queue():
    """
    Runs the process_enrichment_queue scheduled job on-demand.
    Entries with quality >= 0.95 are auto-approved; others remain for review.
    """
    from app.tasks.scheduled_jobs import process_enrichment_queue
    result = await process_enrichment_queue()
    return result


@router.post("/jobs/weekly-review", summary="Manually trigger weekly unverified-entry digest")
async def trigger_weekly_review():
    from app.tasks.scheduled_jobs import weekly_unverified_review
    return weekly_unverified_review()


@router.post("/jobs/cleanup", summary="Manually trigger cleanup of old processed queue entries")
async def trigger_cleanup(retention_days: int = Query(90, ge=7, le=365)):
    from app.tasks.scheduled_jobs import cleanup_old_queue_entries
    return cleanup_old_queue_entries(retention_days=retention_days)
