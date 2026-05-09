"""
Seed the knowledge_base table with high-quality sample resolutions.

Run once:
  cd backend
  python scripts/seed_knowledge_base.py

These are the few-shot examples the Resolution Agent retrieves
via pgvector similarity search. Quality matters — these become
the model's reference for tone, structure, and RBI compliance.
"""

import sys
import os
# Add the 'backend' directory to sys.path so 'app' can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from app.core.config import get_settings
from app.db.supabase_client import get_supabase

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)
supabase = get_supabase()

SEED_DATA = [
    # ── Credit Card ───────────────────────────────────────────────────────
    {
        "category": "Credit Card",
        "resolution_text": (
            "Dear Customer, we acknowledge your concern regarding the unauthorized "
            "transaction on your credit card. As per RBI guidelines on limiting "
            "liability for unauthorized electronic transactions, we have immediately "
            "blocked your card and initiated a chargeback investigation. A provisional "
            "credit will be applied to your account within 10 working days pending "
            "investigation outcome. Please submit a signed dispute form to your "
            "nearest branch within 7 days. Your new card will be dispatched within "
            "5 working days. We sincerely regret this inconvenience."
        ),
        "quality_score": 1.0,
        "tier_level": "branch",
        "tier_scope": "branch_001",
    },
    {
        "category": "Credit Card",
        "resolution_text": (
            "Dear Customer, we have received your complaint regarding the delay in "
            "credit card closure. As per RBI Master Direction on Credit Cards, your "
            "card must be closed within 7 working days of your request. We sincerely "
            "apologize for the delay. Your card has been closed with immediate effect "
            "and the closure confirmation reference is noted. Any pending balance will "
            "be communicated to you within 2 working days. We assure you this will "
            "not be repeated."
        ),
        "quality_score": 1.0,
        "tier_level": "zone",
        "tier_scope": "zone_002",
    },
    {
        "category": "Credit Card",
        "resolution_text": (
            "Dear Customer, thank you for bringing the hidden charges on your credit "
            "card to our attention. We have reviewed your account and confirmed that "
            "the annual fee charged was not disclosed in your Most Important Terms and "
            "Conditions (MITC). As per RBI guidelines, we are reversing this charge "
            "within 3 working days. We have also updated your MITC and will send you "
            "a revised copy for your records."
        ),
        "quality_score": 1.0,
        "tier_level": "national",
        "tier_scope": None,
    },
    # ── UPI / Payments ────────────────────────────────────────────────────
    {
        "category": "UPI / IMPS / NEFT",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the failed UPI "
            "transaction where your account was debited but the beneficiary was not "
            "credited. As per RBI TAT guidelines for failed transactions, the amount "
            "must be reversed within 5 working days. Your refund has been initiated "
            "with reference number noted. If not credited within 5 working days, "
            "a penalty of Rs 100 per day will be applicable as per RBI circular. "
            "We apologize for the inconvenience caused."
        ),
        "quality_score": 1.0,
    },
    {
        "category": "UPI / IMPS / NEFT",
        "resolution_text": (
            "Dear Customer, we have investigated your IMPS transaction failure. "
            "The transaction failed due to a temporary technical issue at the "
            "beneficiary bank. Your amount has been auto-reversed to your account "
            "within the RBI-mandated TAT of T+1 day. We have also waived the "
            "transaction fee as a goodwill gesture. Please retry the transaction "
            "after 30 minutes."
        ),
        "quality_score": 1.0,
    },
    # ── KYC / Account ─────────────────────────────────────────────────────
    {
        "category": "KYC / Account Opening",
        "resolution_text": (
            "Dear Customer, we acknowledge your concern regarding KYC-related issues. "
            "As per RBI KYC Master Direction, customers must be given prior notice "
            "before any account restrictions are applied. Please visit your nearest "
            "branch with your Aadhaar and PAN card to complete the KYC update process. "
            "Alternatively, you can complete Video KYC through our mobile application. "
            "Your account restrictions will be lifted within 24 hours of successful "
            "KYC completion. We regret any inconvenience caused."
        ),
        "quality_score": 1.0,
    },
    {
        "category": "KYC / Account Opening",
        "resolution_text": (
            "Dear Customer, thank you for reaching out regarding your account freeze. "
            "We confirm that your account was placed under restriction for KYC "
            "non-compliance. We apologize for not sending a prior notice as mandated. "
            "Your account has been restored immediately. Please complete your KYC "
            "update within 30 days to avoid future restrictions. Our relationship "
            "manager will contact you within 24 hours to assist."
        ),
        "quality_score": 1.0,
    },
    # ── Loans ─────────────────────────────────────────────────────────────
    {
        "category": "Home Loan",
        "resolution_text": (
            "Dear Customer, we sincerely apologize for the delay in returning your "
            "original property documents post loan closure. As per RBI Responsible "
            "Lending Conduct 2023, these documents must be returned within 30 days "
            "of final repayment. Your documents have been dispatched via registered "
            "post with tracking number provided. If not received within 7 days, "
            "please contact us immediately. A penalty waiver of processing fee has "
            "been applied to your account as compensation for the delay."
        ),
        "quality_score": 1.0,
    },
    {
        "category": "Personal Loan",
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding unfair loan "
            "charges. After investigation, we confirm that the processing fee "
            "deducted during the moratorium period was incorrect as per RBI guidelines. "
            "A full refund of the incorrectly charged amount has been initiated and "
            "will credit to your account within 5 working days. We have also updated "
            "your loan account to reflect the correct interest calculation going forward."
        ),
        "quality_score": 1.0,
    },
    # ── Internet Banking ──────────────────────────────────────────────────
    {
        "category": "Internet Banking / Mobile App",
        "resolution_text": (
            "Dear Customer, we acknowledge your difficulty accessing our mobile "
            "banking application. Our technical team has identified and resolved "
            "the issue affecting login for customers in your region. Please update "
            "the app to version 4.2.1 from the Play Store or App Store and clear "
            "your app cache before retrying. If the issue persists, please call "
            "our 24x7 helpline and quote reference number provided. We apologize "
            "for the disruption to your banking services."
        ),
        "quality_score": 1.0,
    },
    # ── Savings Account ───────────────────────────────────────────────────
    {
        "category": "Savings Account",
        "resolution_text": (
            "Dear Customer, we have investigated your complaint regarding the "
            "incorrect debit from your savings account. Our review confirms that "
            "this was an erroneous charge applied due to a system error. The amount "
            "has been reversed with value dating to the original debit date, ensuring "
            "no loss of interest. We have also applied a goodwill credit of Rs 200 "
            "to your account. We assure you that corrective measures have been "
            "implemented to prevent recurrence."
        ),
        "quality_score": 1.0,
    },
    # ── CIBIL / Credit Bureau ─────────────────────────────────────────────
    {
        "category": "General Banking",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding incorrect "
            "information reported to the credit bureau. As per the Credit Information "
            "Companies Act, we are mandated to update correct information within "
            "30 days of loan/credit card closure. We have submitted a correction "
            "request to CIBIL and Experian effective immediately. Your credit report "
            "will reflect the correct status within 30 days. We apologize for the "
            "distress this may have caused."
        ),
        "quality_score": 1.0,
    },
]


def generate_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        dimensions=settings.openai_embedding_dimension,
    )
    return response.data[0].embedding


def seed():
    print(f"Seeding {len(SEED_DATA)} resolutions into knowledge_base...")
    print(f"Using model: {settings.openai_embedding_model} "
          f"({settings.openai_embedding_dimension} dims)\n")

    success = 0
    failed = 0

    for i, item in enumerate(SEED_DATA, 1):
        try:
            print(f"[{i}/{len(SEED_DATA)}] Seeding: {item['category'][:40]}...")
            embedding = generate_embedding(item["resolution_text"])

            supabase.table("knowledge_base").insert({
                "resolution_text": item["resolution_text"],
                "category": item["category"],
                "source": "seed",
                "quality_score": item["quality_score"],
                "embedding": embedding,
                "tier_level": item["tier_level"],
                "tier_scope": item["tier_scope"],
            }).execute()

            success += 1
            print(f"  ✓ Done")

        except Exception as e:
            failed += 1
            print(f"  ✗ Failed: {e}")

    print(f"\nSeeding complete: {success} success, {failed} failed")
    print(f"Knowledge base now has {success} high-quality resolution templates.")


if __name__ == "__main__":
    seed()