"""
Dashboard Stats API

Powers all frontend chart components:
  GET /api/v1/dashboard/stats          — Main overview stats
  GET /api/v1/dashboard/csat-trends    — CSAT by category/channel/agent
  GET /api/v1/dashboard/agent-performance — Per-agent metrics
  GET /api/v1/dashboard/pipeline-health  — Pipeline success/failure rates
  GET /api/v1/dashboard/root-cause     — Gen-AI batch root cause analysis
"""

import json
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings

router = APIRouter()


@router.get(
    "/stats",
    summary="Main dashboard overview statistics",
)
async def get_dashboard_stats(
    days: int = Query(default=30, description="Lookback window in days"),
):
    """
    Returns all stats needed for the dashboard home page:
    - Complaint volume and routing split
    - Category and sentiment distribution
    - Severity distribution
    - RBI compliance summary
    - Recent pipeline performance
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).isoformat()

    # All complaints in window
    result = (
        supabase.table("complaints")
        .select(
            "complaint_id, category, sentiment, severity, route, "
            "pipeline_status, is_rbi_reportable, compliance_category, "
            "confidence_score, risk_score, status, created_at, channel"
        )
        .gte("created_at", from_date)
        .execute()
    )

    complaints = result.data or []
    total = len(complaints)

    if total == 0:
        return _empty_stats(days)

    # ── Routing split ─────────────────────────────────────────────────────
    auto_count = sum(1 for c in complaints if c.get("route") == "auto_respond")
    human_count = sum(1 for c in complaints if c.get("route") == "human_review")
    pending_count = sum(1 for c in complaints if c.get("pipeline_status") != "complete")

    # ── Category distribution ─────────────────────────────────────────────
    category_dist = {}
    for c in complaints:
        cat = c.get("category") or "Unknown"
        category_dist[cat] = category_dist.get(cat, 0) + 1

    # ── Sentiment distribution ────────────────────────────────────────────
    sentiment_dist = {}
    for c in complaints:
        snt = c.get("sentiment") or "Unknown"
        sentiment_dist[snt] = sentiment_dist.get(snt, 0) + 1

    # ── Severity distribution ─────────────────────────────────────────────
    severity_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for c in complaints:
        sev = c.get("severity") or 3
        if sev in severity_dist:
            severity_dist[sev] += 1

    # ── Channel distribution ──────────────────────────────────────────────
    channel_dist = {}
    for c in complaints:
        ch = c.get("channel") or "unknown"
        channel_dist[ch] = channel_dist.get(ch, 0) + 1

    # ── RBI summary ───────────────────────────────────────────────────────
    rbi_count = sum(1 for c in complaints if c.get("is_rbi_reportable"))

    # ── Avg confidence and risk ───────────────────────────────────────────
    conf_scores = [c["confidence_score"] for c in complaints if c.get("confidence_score")]
    risk_scores = [c["risk_score"] for c in complaints if c.get("risk_score")]

    avg_confidence = round(sum(conf_scores) / len(conf_scores), 3) if conf_scores else 0
    avg_risk = round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0
    avg_severity = round(
        sum(c.get("severity") or 3 for c in complaints) / total, 2
    )

    # ── Daily volume (last 7 days) ────────────────────────────────────────
    daily_volume = _build_daily_volume(complaints, days=7)

    # ── Closed vs open ───────────────────────────────────────────────────
    closed = sum(1 for c in complaints if c.get("status") in ("closed", "resolved"))
    open_count = total - closed - pending_count

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "overview": {
            "total_complaints": total,
            "auto_responded": auto_count,
            "human_review": human_count,
            "pending_pipeline": pending_count,
            "auto_respond_rate_percent": round(auto_count / total * 100, 1),
            "rbi_reportable": rbi_count,
            "rbi_reportable_rate_percent": round(rbi_count / total * 100, 1),
            "closed": closed,
            "open": open_count,
        },
        "averages": {
            "avg_severity": avg_severity,
            "avg_confidence_score": avg_confidence,
            "avg_risk_score": avg_risk,
        },
        "distributions": {
            "by_category": [
                {"category": k, "count": v, "percent": round(v / total * 100, 1)}
                for k, v in sorted(
                    category_dist.items(), key=lambda x: x[1], reverse=True
                )
            ],
            "by_sentiment": [
                {"sentiment": k, "count": v, "percent": round(v / total * 100, 1)}
                for k, v in sorted(
                    sentiment_dist.items(), key=lambda x: x[1], reverse=True
                )
            ],
            "by_severity": [
                {
                    "severity": k,
                    "label": {1: "Low", 2: "Moderate", 3: "High",
                              4: "Critical", 5: "Emergency"}[k],
                    "count": v,
                    "percent": round(v / total * 100, 1),
                }
                for k, v in severity_dist.items()
            ],
            "by_channel": [
                {"channel": k, "count": v, "percent": round(v / total * 100, 1)}
                for k, v in sorted(
                    channel_dist.items(), key=lambda x: x[1], reverse=True
                )
            ],
        },
        "daily_volume": daily_volume,
    }


@router.get(
    "/csat-trends",
    summary="CSAT trends by category, channel, and agent",
)
async def get_csat_trends(
    days: int = Query(default=30, description="Lookback window in days"),
):
    """
    Returns CSAT analytics for the dashboard:
    - Overall average CSAT
    - CSAT by complaint category
    - CSAT by channel
    - CSAT by resolution type (auto vs human)
    - Weekly CSAT trend
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).isoformat()

    # Fetch customer feedback with complaint metadata
    fb_result = (
        supabase.table("customer_feedback")
        .select(
            "complaint_id, rating, feedback_sentiment, "
            "resolution_type, agent_id, issue_tags, created_at"
        )
        .gte("created_at", from_date)
        .execute()
    )

    feedbacks = fb_result.data or []

    if not feedbacks:
        return {
            "period_days": days,
            "message": "No customer feedback recorded yet.",
            "total_responses": 0,
        }

    # Fetch complaint metadata for category + channel
    complaint_ids = [f["complaint_id"] for f in feedbacks]
    complaints_result = (
        supabase.table("complaints")
        .select("complaint_id, category, channel")
        .in_("complaint_id", complaint_ids)
        .execute()
    )

    complaint_map = {
        c["complaint_id"]: c
        for c in (complaints_result.data or [])
    }

    # ── Overall CSAT ──────────────────────────────────────────────────────
    all_ratings = [f["rating"] for f in feedbacks]
    overall_avg = round(sum(all_ratings) / len(all_ratings), 2)

    # ── CSAT by category ──────────────────────────────────────────────────
    by_category: dict[str, list] = {}
    by_channel: dict[str, list] = {}
    by_resolution_type: dict[str, list] = {}
    issue_tag_freq: dict[str, int] = {}

    for fb in feedbacks:
        cid = fb["complaint_id"]
        complaint_info = complaint_map.get(cid, {})
        cat = complaint_info.get("category", "Unknown")
        ch = complaint_info.get("channel", "unknown")
        rt = fb.get("resolution_type", "unknown")
        rating = fb["rating"]

        by_category.setdefault(cat, []).append(rating)
        by_channel.setdefault(ch, []).append(rating)
        by_resolution_type.setdefault(rt, []).append(rating)

        for tag in (fb.get("issue_tags") or []):
            issue_tag_freq[tag] = issue_tag_freq.get(tag, 0) + 1

    def avg_list(lst): return round(sum(lst) / len(lst), 2) if lst else 0

    # ── Weekly trend ──────────────────────────────────────────────────────
    weekly_trend = _build_weekly_csat_trend(feedbacks, weeks=4)

    # ── Satisfaction distribution ─────────────────────────────────────────
    sat_dist = {
        "very_dissatisfied": sum(1 for r in all_ratings if r == 1),
        "dissatisfied": sum(1 for r in all_ratings if r == 2),
        "neutral": sum(1 for r in all_ratings if r == 3),
        "satisfied": sum(1 for r in all_ratings if r == 4),
        "very_satisfied": sum(1 for r in all_ratings if r == 5),
    }

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "overall": {
            "total_responses": len(feedbacks),
            "average_csat": overall_avg,
            "csat_label": _csat_label(overall_avg),
        },
        "satisfaction_distribution": sat_dist,
        "by_category": [
            {
                "category": cat,
                "avg_csat": avg_list(ratings),
                "response_count": len(ratings),
                "csat_label": _csat_label(avg_list(ratings)),
            }
            for cat, ratings in sorted(
                by_category.items(),
                key=lambda x: avg_list(x[1])
            )
        ],
        "by_channel": [
            {
                "channel": ch,
                "avg_csat": avg_list(ratings),
                "response_count": len(ratings),
            }
            for ch, ratings in sorted(
                by_channel.items(),
                key=lambda x: avg_list(x[1]),
                reverse=True
            )
        ],
        "by_resolution_type": {
            rt: {
                "avg_csat": avg_list(ratings),
                "count": len(ratings),
            }
            for rt, ratings in by_resolution_type.items()
        },
        "top_issue_tags": sorted(
            [{"tag": k, "count": v} for k, v in issue_tag_freq.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "weekly_trend": weekly_trend,
    }


@router.get(
    "/agent-performance",
    summary="Per-agent performance metrics",
)
async def get_agent_performance(
    days: int = Query(default=30, description="Lookback window in days"),
):
    """
    Returns per-agent metrics:
    - Total complaints handled
    - Accept / edit / reject / escalate rates
    - Average CSAT for their resolved complaints
    - Knowledge base contribution count
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).isoformat()

    agent_fb_result = (
        supabase.table("agent_feedback")
        .select("agent_id, action, agent_score, complaint_id, created_at")
        .gte("created_at", from_date)
        .execute()
    )

    feedbacks = agent_fb_result.data or []

    if not feedbacks:
        return {
            "period_days": days,
            "message": "No agent feedback recorded yet.",
            "agents": [],
        }

    # Group by agent
    agents: dict[str, dict] = {}
    for fb in feedbacks:
        aid = fb["agent_id"]
        if aid not in agents:
            agents[aid] = {
                "agent_id": aid,
                "total_handled": 0,
                "accept_count": 0,
                "edit_count": 0,
                "reject_count": 0,
                "escalate_count": 0,
                "complaint_ids": [],
                "total_score": 0.0,
            }
        agents[aid]["total_handled"] += 1
        agents[aid]["total_score"] += fb.get("agent_score", 0)
        agents[aid]["complaint_ids"].append(fb["complaint_id"])
        action = fb.get("action", "")
        if action == "accept":
            agents[aid]["accept_count"] += 1
        elif action == "edit":
            agents[aid]["edit_count"] += 1
        elif action == "reject":
            agents[aid]["reject_count"] += 1
        elif action == "escalate":
            agents[aid]["escalate_count"] += 1

    # Fetch CSAT for each agent's complaints
    all_cids = [cid for a in agents.values() for cid in a["complaint_ids"]]
    if all_cids:
        csat_result = (
            supabase.table("customer_feedback")
            .select("complaint_id, rating, agent_id")
            .in_("complaint_id", all_cids)
            .execute()
        )
        csat_map: dict[str, list] = {}
        for r in (csat_result.data or []):
            aid = r.get("agent_id")
            if aid:
                csat_map.setdefault(aid, []).append(r["rating"])
    else:
        csat_map = {}

    result = []
    for aid, data in agents.items():
        total = data["total_handled"]
        csat_ratings = csat_map.get(aid, [])
        result.append({
            "agent_id": aid,
            "total_handled": total,
            "accept_rate": round(data["accept_count"] / total * 100, 1),
            "edit_rate": round(data["edit_count"] / total * 100, 1),
            "reject_rate": round(data["reject_count"] / total * 100, 1),
            "escalate_rate": round(data["escalate_count"] / total * 100, 1),
            "avg_agent_score": round(data["total_score"] / total, 3),
            "avg_csat": round(sum(csat_ratings) / len(csat_ratings), 2) if csat_ratings else None,
            "csat_response_count": len(csat_ratings),
        })

    # Sort by avg_agent_score descending
    result.sort(key=lambda x: x["avg_agent_score"], reverse=True)

    return {
        "period_days": days,
        "total_agents": len(result),
        "agents": result,
    }


@router.get(
    "/pipeline-health",
    summary="Pipeline success, failure and latency metrics",
)
async def get_pipeline_health(
    days: int = Query(default=7, description="Lookback window in days"),
):
    """
    Returns pipeline health metrics:
    - Total pipeline runs
    - Success / failure / pending rates
    - Agent-level failure frequency
    - Average pipeline duration per agent
    """
    supabase = get_supabase()
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=days)).isoformat()

    # All agent decisions in window
    decisions_result = (
        supabase.table("agent_decisions")
        .select("agent_name, agent_order, status, duration_ms, created_at")
        .gte("created_at", from_date)
        .execute()
    )

    decisions = [
        d for d in (decisions_result.data or [])
        if d.get("status") in ("complete", "failed")
    ]

    if not decisions:
        return {
            "period_days": days,
            "message": "No pipeline runs in this period.",
        }

    # Per-agent stats
    agent_stats: dict[str, dict] = {}
    for d in decisions:
        name = d["agent_name"]
        if name not in agent_stats:
            agent_stats[name] = {
                "agent_name": name,
                "agent_order": d.get("agent_order"),
                "total_runs": 0,
                "success_count": 0,
                "failure_count": 0,
                "durations_ms": [],
            }
        agent_stats[name]["total_runs"] += 1
        if d["status"] == "complete":
            agent_stats[name]["success_count"] += 1
        else:
            agent_stats[name]["failure_count"] += 1
        if d.get("duration_ms") and d["duration_ms"] > 0:
            agent_stats[name]["durations_ms"].append(d["duration_ms"])

    agents_list = []
    for name, stats in agent_stats.items():
        durations = stats["durations_ms"]
        agents_list.append({
            "agent_name": name,
            "agent_order": stats["agent_order"],
            "total_runs": stats["total_runs"],
            "success_rate": round(
                stats["success_count"] / stats["total_runs"] * 100, 1
            ),
            "failure_count": stats["failure_count"],
            "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
        })

    agents_list.sort(key=lambda x: x["agent_order"] or 99)

    total_runs = len(set(
        d.get("created_at", "")[:10]
        for d in decisions
    ))

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "summary": {
            "total_agent_executions": len(decisions),
            "overall_success_rate": round(
                sum(1 for d in decisions if d["status"] == "complete")
                / len(decisions) * 100, 1
            ),
            "total_failures": sum(
                1 for d in decisions if d["status"] == "failed"
            ),
        },
        "per_agent": agents_list,
    }


@router.post(
    "/root-cause",
    summary="Gen-AI batch root cause analysis on low-rated complaints",
)
async def get_root_cause_analysis(
    min_rating: int = Query(default=2, description="Analyse complaints with rating ≤ this"),
    limit: int = Query(default=50, description="Max complaints to analyse"),
):
    """
    Batch-analyses low-rated complaints using GPT-4o to identify
    systemic patterns and root causes.

    This is the trend analysis feature from the original brief:
    'Root cause identification across complaint data'

    Returns:
    - Top root causes across low-rated complaints
    - Most affected categories and channels
    - One concrete recommendation per root cause
    - Sentiment pattern analysis
    """
    supabase = get_supabase()

    # Fetch low-rated customer feedback
    fb_result = (
        supabase.table("customer_feedback")
        .select("complaint_id, rating, issue_tags, masked_feedback_text")
        .lte("rating", min_rating)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    feedbacks = fb_result.data or []

    if len(feedbacks) < 3:
        return {
            "message": f"Not enough low-rated complaints to analyse. "
                       f"Found {len(feedbacks)}, need at least 3.",
            "total_analysed": len(feedbacks),
        }

    # Fetch complaint details for context
    cids = [f["complaint_id"] for f in feedbacks]
    complaints_result = (
        supabase.table("complaints")
        .select("complaint_id, masked_text, category, channel, compliance_category")
        .in_("complaint_id", cids)
        .execute()
    )

    complaint_map = {
        c["complaint_id"]: c
        for c in (complaints_result.data or [])
    }

    # Build summary for GPT-4o
    summaries = []
    for fb in feedbacks[:30]:  # cap at 30 to stay within context
        cid = fb["complaint_id"]
        c = complaint_map.get(cid, {})
        summaries.append(
            f"[{c.get('category', 'Unknown')} | {c.get('channel', 'unknown')} | "
            f"Rating: {fb['rating']}/5 | Tags: {fb.get('issue_tags', [])}]\n"
            f"Complaint: {(c.get('masked_text') or '')[:200]}\n"
            f"Feedback: {fb.get('masked_feedback_text') or 'No text'}"
        )

    complaints_text = "\n\n---\n\n".join(summaries)

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    prompt = f"""You are a customer experience analyst at an Indian bank.

Below are {len(feedbacks)} customer complaints that received low satisfaction 
ratings (1-{min_rating} stars out of 5):

{complaints_text}

Analyse these complaints and identify:

1. TOP ROOT CAUSES (3-5): What systemic issues caused customer dissatisfaction?
2. MOST AFFECTED AREAS: Which categories and channels have the most issues?
3. RECOMMENDATIONS: One concrete actionable fix per root cause
4. URGENCY: Which root cause needs immediate attention?

Respond ONLY with this JSON structure:
{{
  "root_causes": [
    {{
      "rank": 1,
      "title": "<short title>",
      "description": "<2 sentence description>",
      "affected_categories": ["<category>"],
      "frequency_estimate": "<percentage of complaints affected>",
      "recommendation": "<specific actionable fix>",
      "urgency": "HIGH | MEDIUM | LOW"
    }}
  ],
  "most_affected": {{
    "categories": ["<category1>", "<category2>"],
    "channels": ["<channel1>"]
  }},
  "immediate_action": "<single most urgent action to take today>",
  "analysis_confidence": <float 0.0-1.0>
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1000,
        )
        analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Root cause analysis failed: {str(e)}"
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_complaints_analysed": len(feedbacks),
        "rating_threshold": min_rating,
        "analysis": analysis,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_stats(days: int) -> dict:
    return {
        "period_days": days,
        "message": "No complaints found in this period.",
        "overview": {
            "total_complaints": 0,
            "auto_responded": 0,
            "human_review": 0,
        },
    }


def _csat_label(avg: float) -> str:
    if avg >= 4.5:
        return "Excellent"
    if avg >= 3.5:
        return "Good"
    if avg >= 2.5:
        return "Neutral"
    if avg >= 1.5:
        return "Poor"
    return "Critical"


def _build_daily_volume(complaints: list, days: int) -> list:
    """Build daily complaint counts for the last N days."""
    now = datetime.now(timezone.utc)
    result = []
    for i in range(days - 1, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        count = sum(
            1 for c in complaints
            if (c.get("created_at") or "").startswith(day_str)
        )
        result.append({"date": day_str, "count": count})
    return result


def _build_weekly_csat_trend(feedbacks: list, weeks: int) -> list:
    """Build weekly average CSAT for the last N weeks."""
    now = datetime.now(timezone.utc)
    result = []
    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        week_label = week_start.strftime("%b %d")
        week_ratings = []
        for fb in feedbacks:
            created = fb.get("created_at", "")
            if not created:
                continue
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if week_start <= dt < week_end:
                    week_ratings.append(fb["rating"])
            except Exception:
                continue
        result.append({
            "week": week_label,
            "avg_csat": round(
                sum(week_ratings) / len(week_ratings), 2
            ) if week_ratings else None,
            "response_count": len(week_ratings),
        })
    return result