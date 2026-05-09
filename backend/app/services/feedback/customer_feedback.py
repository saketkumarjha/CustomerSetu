"""
Customer Feedback Service — CSAT Loop

Handles the external satisfaction signal:
  Customer rates 1-5 stars after complaint resolution
  → Presidio masks free-text feedback
  → Sentiment analysis on masked feedback
  → Combined RL score = (agent × 0.4) + (customer × 0.6)
  → Router calibration if CSAT drops below threshold
  → High-rated resolutions promoted to knowledge base

Customer carries 60% weight because they are the
ultimate judge of whether their complaint was resolved.
An internal agent approving a draft does not mean
the customer is satisfied.
"""

from openai import OpenAI
from app.db.supabase_client import get_supabase
from app.core.config import get_settings
from app.services.agents.pii_agent import run_pii_detection

CSAT_CALIBRATION_THRESHOLD = 3.0
CALIBRATION_SAMPLE_SIZE = 50


def process_customer_feedback(
    complaint_id: str,
    customer_id: str,
    rating: int,
    issue_tags: list[str],
    feedback_text: str | None,
) -> dict:
    """
    Process customer CSAT feedback.

    Steps:
    1. Validate rating (1-5)
    2. Mask PII in free-text feedback
    3. Sentiment analysis on masked feedback
    4. Fetch agent_score from agent_feedback table
    5. Calculate combined RL score
    6. Store in customer_feedback table
    7. Update fine_tune_dataset with customer rating
    8. Trigger router calibration check
    9. Auto-promote to KB if combined score is high
    """
    supabase = get_supabase()

    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5")

    # Fetch complaint for metadata
    complaint_result = (
        supabase.table("complaints")
        .select("category, route, masked_text, compliance_category")
        .eq("complaint_id", complaint_id)
        .execute()
    )

    if not complaint_result.data:
        raise ValueError(f"Complaint {complaint_id} not found")

    complaint = complaint_result.data[0]
    category = complaint.get("category", "General Banking")
    resolution_type = complaint.get("route", "human_review")

    # Step 2: Mask PII in free-text feedback
    masked_feedback = None
    feedback_sentiment = None

    if feedback_text:
        pii_result = run_pii_detection(feedback_text)
        masked_feedback = pii_result["masked_text"]

        # Sentiment analysis on masked feedback
        feedback_sentiment = _analyze_feedback_sentiment(masked_feedback)

    # Step 3: Fetch agent_score
    agent_fb_result = (
        supabase.table("agent_feedback")
        .select("agent_score, agent_id")
        .eq("complaint_id", complaint_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    agent_score = 0.5  # default if no agent feedback yet
    agent_id = None
    if agent_fb_result.data:
        agent_score = agent_fb_result.data[0].get("agent_score", 0.5)
        agent_id = agent_fb_result.data[0].get("agent_id")

    # Step 4: Combined RL score
    # Normalise rating to 0.0-1.0
    customer_score_normalised = (rating - 1) / 4
    combined_rl_score = round(
        (agent_score * 0.4) + (customer_score_normalised * 0.6), 4
    )

    # Step 5: Store feedback
    supabase.table("customer_feedback").insert({
        "complaint_id": complaint_id,
        "customer_id": customer_id,
        "rating": rating,
        "issue_tags": issue_tags,
        "feedback_text": feedback_text,
        "masked_feedback_text": masked_feedback,
        "feedback_sentiment": feedback_sentiment,
        "resolution_type": resolution_type,
        "agent_id": agent_id,
        "combined_rl_score": combined_rl_score,
    }).execute()

    # Step 6: Update fine_tune_dataset with customer rating
    supabase.table("fine_tune_dataset").update({
        "customer_rating": rating,
        "combined_score": combined_rl_score,
    }).eq("complaint_id", complaint_id).execute()

    # Step 7: Update complaint status to closed
    supabase.table("complaints").update(
        {"status": "closed"}
    ).eq("complaint_id", complaint_id).execute()

    # Update KB enrichment queue quality signals with CSAT (best-effort)
    try:
        from app.services.resolution_event_handler import resolution_event_handler
        resolution_event_handler.on_customer_feedback(
            complaint_id = complaint_id,
            rating       = float(rating),
            comment      = feedback_text or "",
        )
    except Exception:
        pass

    # Step 8: Router calibration
    calibration_triggered = _check_router_calibration(
        category=category,
        resolution_type=resolution_type,
    )

    # Step 9: Auto-promote to KB if high combined score
    kb_promoted = False
    if combined_rl_score >= 0.85:
        kb_promoted = _promote_high_rated_resolution(complaint_id, combined_rl_score)

    return {
        "complaint_id": complaint_id,
        "customer_id": customer_id,
        "rating": rating,
        "combined_rl_score": combined_rl_score,
        "score_breakdown": {
            "agent_score": agent_score,
            "agent_weight": "40%",
            "customer_score_normalised": round(customer_score_normalised, 4),
            "customer_weight": "60%",
        },
        "feedback_sentiment": feedback_sentiment,
        "calibration_triggered": calibration_triggered,
        "kb_promoted": kb_promoted,
        "status": "recorded",
    }


def _analyze_feedback_sentiment(masked_text: str) -> str:
    """
    Lightweight sentiment analysis on customer feedback text.
    Uses GPT-4o with a simple single-word output requirement.
    """
    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze sentiment of this customer feedback. "
                        "Reply with ONE word only: "
                        "Positive, Neutral, Negative, or Mixed"
                    ),
                },
                {"role": "user", "content": masked_text},
            ],
            max_tokens=5,
            temperature=0.0,
        )
        sentiment = response.choices[0].message.content.strip()
        valid = {"Positive", "Neutral", "Negative", "Mixed"}
        return sentiment if sentiment in valid else "Neutral"

    except Exception:
        return "Neutral"


def _check_router_calibration(
    category: str,
    resolution_type: str,
) -> bool:
    """
    Check if auto-responded complaints in this category
    are getting consistently low ratings.

    If average CSAT < 3.0 for last 50 auto-responded complaints
    in this category → raise routing threshold → more go to human review.

    This is how the routing system improves over time
    based on real customer outcomes — not just agent opinions.
    """
    if resolution_type != "auto_respond":
        return False

    supabase = get_supabase()

    try:
        # Get last 50 auto-responded complaints in this category with ratings
        recent_result = (
            supabase.table("customer_feedback")
            .select("rating, complaint_id")
            .limit(CALIBRATION_SAMPLE_SIZE)
            .order("created_at", desc=True)
            .execute()
        )

        if not recent_result.data or len(recent_result.data) < 5:
            return False  # not enough data yet

        ratings = [r["rating"] for r in recent_result.data]
        avg_csat = sum(ratings) / len(ratings)

        if avg_csat < CSAT_CALIBRATION_THRESHOLD:
            # Update router_config — raise threshold for this category
            current = (
                supabase.table("router_config")
                .select("min_auto_score")
                .eq("category", category)
                .execute()
            )

            if current.data:
                current_threshold = current.data[0].get("min_auto_score", 4.0)
                new_threshold = min(current_threshold + 0.5, 7.0)
                supabase.table("router_config").update({
                    "min_auto_score": new_threshold,
                }).eq("category", category).execute()

                print(
                    f"[CALIBRATION] {category} threshold raised "
                    f"{current_threshold} → {new_threshold} "
                    f"(avg CSAT: {avg_csat:.2f})"
                )
                return True

    except Exception as e:
        print(f"[CALIBRATION] Error: {e}")

    return False


def _promote_high_rated_resolution(
    complaint_id: str,
    combined_score: float,
) -> bool:
    """
    If combined RL score >= 0.85 (agent approved + customer loved it),
    add the final response to the knowledge base.

    This is the highest-confidence signal —
    both the internal agent AND the customer confirmed this was good.
    """
    supabase = get_supabase()

    try:
        # Fetch the final response from agent_feedback
        agent_fb = (
            supabase.table("agent_feedback")
            .select("final_response, agent_score")
            .eq("complaint_id", complaint_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not agent_fb.data or not agent_fb.data[0].get("final_response"):
            return False

        final_response = agent_fb.data[0]["final_response"]

        # Fetch category
        complaint = (
            supabase.table("complaints")
            .select("category")
            .eq("complaint_id", complaint_id)
            .execute()
        )
        category = complaint.data[0].get("category", "General Banking") if complaint.data else "General Banking"

        # Promote with quality score based on combined RL score
        from app.services.feedback.agent_feedback import _promote_to_knowledge_base
        _promote_to_knowledge_base(
            resolution_text=final_response,
            category=category,
            quality_score=combined_score,
        )
        return True

    except Exception as e:
        print(f"[KB_PROMOTION] Error: {e}")
        return False