"""
Seed the knowledge_base table with high-quality sample resolutions.

Run once:
  cd backend
  python -m app.scripts.seed_knowledge_base

These are the few-shot examples the Resolution Agent retrieves
via pgvector similarity search. Quality matters — these become
the model's reference for tone, structure, and RBI compliance.

Fixes applied:
  - verified = True  (retrieve_context filters on this)
  - tier_level = int (1-4, not strings)
  - Category names match Agent 3 (Classification Agent) output exactly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from app.core.config import get_settings
from app.db.supabase_client import get_supabase

settings = get_settings()
client   = OpenAI(api_key=settings.openai_api_key)
supabase = get_supabase()

# tier_level: 1=Branch, 2=Zone, 3=Region, 4=Head Office
# category: must match Agent 3 (Classification Agent) output exactly

SEED_DATA = [

    # ── UPI ───────────────────────────────────────────────────────────────────
    {
        "category": "UPI",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the failed UPI "
            "transaction where your account was debited but the beneficiary was not "
            "credited. As per RBI TAT guidelines for failed transactions, the amount "
            "must be auto-reversed within T+1 working day. Your refund has been "
            "initiated and will reflect within 5 working days. If not credited, "
            "a penalty of Rs 100 per day will be applicable as per RBI circular "
            "DPSS.CO.OD No.629/06.08.005/2019-20. We sincerely apologize for the "
            "inconvenience caused."
        ),
    },
    {
        "category": "UPI",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have investigated your complaint of duplicate UPI "
            "debit. Our records confirm two identical transactions were processed "
            "due to a technical timeout. The duplicate debit of Rs [AMOUNT] has "
            "been reversed to your account with value dating to the original debit "
            "date to ensure no loss of interest. Please allow 2 working days for "
            "the reversal to reflect. We regret the inconvenience."
        ),
    },

    # ── ATM ───────────────────────────────────────────────────────────────────
    {
        "category": "ATM",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the ATM "
            "transaction where cash was not dispensed but your account was debited. "
            "As per RBI guidelines, failed ATM transactions must be resolved within "
            "5 working days. Your account has been credited with the disputed amount "
            "as a provisional credit pending ATM cash reconciliation. If the cash "
            "count confirms a surplus, the credit will be made permanent. We "
            "apologize for the distress caused."
        ),
    },
    {
        "category": "ATM",
        "tier_level": 1,
        "quality_score": 0.95,
        "resolution_text": (
            "Dear Customer, thank you for reporting the unauthorized ATM withdrawal. "
            "We have immediately blocked your card to prevent further misuse. A "
            "chargeback has been filed and provisional credit will be applied within "
            "10 working days as per RBI guidelines on limiting liability. Please "
            "visit your nearest branch with your ID proof to collect a replacement "
            "card. We have also filed an incident report with our fraud team."
        ),
    },

    # ── Debit Card ────────────────────────────────────────────────────────────
    {
        "category": "Debit Card",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the unauthorized "
            "debit card transaction. As per RBI circular on limiting liability for "
            "unauthorized transactions, we have blocked your card immediately. A "
            "provisional credit has been applied to your account within 10 working "
            "days. Your new debit card will be dispatched within 5 working days. "
            "Please submit a signed declaration to your home branch to complete "
            "the chargeback process."
        ),
    },
    {
        "category": "Debit Card",
        "tier_level": 1,
        "quality_score": 0.95,
        "resolution_text": (
            "Dear Customer, we have received your request for debit card hotlisting. "
            "Your card ending [LAST4] has been blocked with immediate effect to "
            "prevent unauthorized usage. A replacement card has been ordered and "
            "will be delivered to your registered address within 7 working days. "
            "Your PIN will remain the same unless you choose to reset it via our "
            "ATM or mobile banking. We regret the inconvenience."
        ),
    },

    # ── Credit Card ───────────────────────────────────────────────────────────
    {
        "category": "Credit Card",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the unauthorized "
            "credit card transaction. As per RBI guidelines on limiting liability, "
            "your card has been blocked and a chargeback investigation initiated. "
            "A provisional credit will be applied within 10 working days. The "
            "dispute will be resolved within 30 days as per card network rules. "
            "Please submit a dispute form at your nearest branch. We sincerely "
            "regret this experience."
        ),
    },
    {
        "category": "Credit Card",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding hidden charges "
            "on your credit card. After investigation, we confirm the annual fee "
            "was not disclosed in your Most Important Terms and Conditions (MITC) "
            "at the time of issuance, which is a violation of RBI fair practice "
            "guidelines. The charge of Rs [AMOUNT] has been reversed immediately. "
            "We have updated your MITC and will send a revised copy within 3 days."
        ),
    },

    # ── Home Loan ─────────────────────────────────────────────────────────────
    {
        "category": "Home Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we sincerely apologize for the delay in returning your "
            "original property documents post loan closure. As per RBI Responsible "
            "Lending Conduct Directions 2023, original documents must be returned "
            "within 30 days of final repayment. Your documents have been dispatched "
            "via registered post. Tracking details have been shared on your "
            "registered mobile. A processing fee waiver has been applied as "
            "compensation. We assure you this will not recur."
        ),
    },
    {
        "category": "Home Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding incorrect "
            "interest rate applied to your home loan. Our investigation confirms "
            "the MCLR-linked rate was not reset on the due date as per your loan "
            "agreement. The excess interest of Rs [AMOUNT] has been credited to "
            "your loan account with value dating. Your EMI has been recalculated "
            "at the correct rate and the revised schedule sent to your email. "
            "We apologize for this oversight."
        ),
    },

    # ── Personal Loan ─────────────────────────────────────────────────────────
    {
        "category": "Personal Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding unfair loan "
            "charges. After investigation, we confirm the processing fee deducted "
            "during the moratorium period was incorrect as per RBI guidelines. A "
            "full refund of Rs [AMOUNT] has been initiated and will credit to your "
            "account within 5 working days. Your loan account has been updated to "
            "reflect the correct interest calculation going forward."
        ),
    },
    {
        "category": "Personal Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your grievance regarding prepayment "
            "charges levied on your personal loan. As per RBI guidelines, "
            "foreclosure charges cannot be levied on floating rate personal loans. "
            "The prepayment penalty of Rs [AMOUNT] charged to your account has "
            "been reversed with immediate effect. Your loan closure NOC will be "
            "issued within 7 working days. We regret the inconvenience."
        ),
    },

    # ── Business Loan ─────────────────────────────────────────────────────────
    {
        "category": "Business Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "disbursement of your approved business loan. Our records confirm the "
            "disbursement was held due to a documentation mismatch. We have "
            "resolved the discrepancy and the loan amount of Rs [AMOUNT] will be "
            "credited to your account within 2 working days. We apologize for the "
            "delay and assure prompt resolution."
        ),
    },
    {
        "category": "Business Loan",
        "tier_level": 2,
        "quality_score": 0.95,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding the interest "
            "rate revision on your business loan. Our investigation confirms the "
            "rate revision notice was not sent 3 months in advance as required by "
            "your loan agreement. The rate has been restored to the previous level "
            "for the period of notice failure and excess interest reversed. The "
            "revised loan statement has been emailed to you."
        ),
    },

    # ── Savings Account ───────────────────────────────────────────────────────
    {
        "category": "Savings Account",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have investigated your complaint regarding the "
            "incorrect debit from your savings account. Our review confirms this "
            "was an erroneous charge applied due to a system error. The amount of "
            "Rs [AMOUNT] has been reversed with value dating to the original debit "
            "date, ensuring no loss of interest. A goodwill credit of Rs 200 has "
            "also been applied. We assure corrective measures have been implemented."
        ),
    },
    {
        "category": "Savings Account",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding non-credit of "
            "interest on your savings account. As per RBI guidelines, savings "
            "account interest must be credited on a quarterly basis. We confirm "
            "the interest of Rs [AMOUNT] for the quarter ending [DATE] was not "
            "credited due to a system error. The amount has been credited with "
            "retrospective value dating. We apologize for the oversight."
        ),
    },

    # ── Current Account ───────────────────────────────────────────────────────
    {
        "category": "Current Account",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding incorrect "
            "service charges levied on your current account. After investigation, "
            "we confirm the charges were applied in error as your account maintains "
            "the minimum quarterly average balance. The service charge of Rs [AMOUNT] "
            "has been reversed. We have flagged your account to prevent recurrence "
            "and apologize for the inconvenience."
        ),
    },

    # ── Internet Banking ──────────────────────────────────────────────────────
    {
        "category": "Internet Banking",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the unauthorized "
            "transaction conducted via internet banking. We have immediately blocked "
            "your internet banking access to prevent further misuse. A cybercrime "
            "complaint reference has been logged. As per RBI guidelines on limited "
            "liability, a provisional credit will be applied within 10 working days "
            "pending investigation. Please reset your credentials at your nearest "
            "branch with valid ID proof."
        ),
    },
    {
        "category": "Internet Banking",
        "tier_level": 1,
        "quality_score": 0.95,
        "resolution_text": (
            "Dear Customer, we acknowledge your difficulty accessing our internet "
            "banking portal. Our technical team has identified and resolved the "
            "server-side issue affecting login. Please clear your browser cache "
            "and retry. If the issue persists, please call our 24x7 helpline "
            "quoting your complaint reference number. We apologize for the "
            "disruption to your banking services."
        ),
    },

    # ── Mobile Banking ────────────────────────────────────────────────────────
    {
        "category": "Mobile Banking",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your difficulty accessing our mobile "
            "banking application. Our technical team has identified and resolved "
            "the issue affecting login for customers in your region. Please update "
            "the app to the latest version from the Play Store or App Store and "
            "clear your app cache before retrying. If the issue persists, please "
            "call our 24x7 helpline quoting the complaint reference number. We "
            "apologize for the disruption to your banking services."
        ),
    },

    # ── KYC ───────────────────────────────────────────────────────────────────
    {
        "category": "KYC",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your concern regarding KYC-related "
            "account restrictions. As per RBI KYC Master Direction 2016, customers "
            "must receive prior notice before any account restrictions are applied. "
            "We apologize for not following this procedure. Your account restrictions "
            "have been lifted immediately. Please complete your KYC update within "
            "30 days by visiting your nearest branch with Aadhaar and PAN, or via "
            "Video KYC on our mobile app. We regret the inconvenience."
        ),
    },
    {
        "category": "KYC",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have received your complaint regarding repeated KYC "
            "requests despite prior submission. Our records confirm your KYC "
            "documents were submitted on [DATE] but were not updated in the system "
            "due to a processing error. Your KYC has been updated with immediate "
            "effect. Your account is now fully operational. We apologize for the "
            "repeated inconvenience and have raised an internal ticket to prevent "
            "future recurrence."
        ),
    },

    # ── Cheque ────────────────────────────────────────────────────────────────
    {
        "category": "Cheque",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the wrongful "
            "dishonour of your cheque. Our investigation confirms the cheque was "
            "dishonoured due to a system error despite sufficient funds in your "
            "account. We have issued a letter of regret to the payee on your behalf "
            "and waived all dishonour charges. We sincerely apologize for the "
            "reputational inconvenience caused and have taken corrective steps."
        ),
    },
    {
        "category": "Cheque",
        "tier_level": 1,
        "quality_score": 0.95,
        "resolution_text": (
            "Dear Customer, we have investigated your complaint regarding delay in "
            "cheque collection. The cheque deposited on [DATE] was delayed due to "
            "a courier disruption in the clearing cycle. The proceeds of Rs [AMOUNT] "
            "have been credited to your account with value dating to the original "
            "deposit date. Delayed credit interest of Rs [INTEREST] has also been "
            "applied. We apologize for the inconvenience."
        ),
    },

    # ── Locker ────────────────────────────────────────────────────────────────
    {
        "category": "Locker",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the locker "
            "facility. As per RBI revised guidelines on safe deposit lockers "
            "effective January 2023, banks are responsible for maintaining the "
            "integrity of the locker room. We have inspected your locker and "
            "confirmed it is secure. The locker rent overcharge of Rs [AMOUNT] "
            "has been reversed. Your locker agreement has been renewed as per "
            "the revised RBI model agreement. We apologize for the concern caused."
        ),
    },

    # ── General Banking ───────────────────────────────────────────────────────
    {
        "category": "General Banking",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding incorrect "
            "information reported to the credit bureau. As per the Credit "
            "Information Companies Act, we are mandated to update correct "
            "information within 30 days of loan or credit card closure. We "
            "have submitted a correction request to CIBIL and Experian with "
            "immediate effect. Your credit report will reflect the correct status "
            "within 30 days. We apologize for the distress this may have caused."
        ),
    },
    {
        "category": "General Banking",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have received your complaint and sincerely apologize "
            "for the unsatisfactory service you experienced at our branch. We have "
            "shared your feedback with the Branch Manager for immediate corrective "
            "action. Staff training has been reinforced. We assure you that such "
            "conduct is not in keeping with our service standards. Please feel free "
            "to contact us at any time if you have further concerns."
        ),
    },
    {
        "category": "General Banking",
        "tier_level": 4,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge receipt of your grievance at our Nodal "
            "Officer level. Your complaint has been reviewed by our Head Office "
            "Grievance Cell in accordance with RBI guidelines on internal grievance "
            "redressal. We have directed the concerned department to resolve this "
            "matter with priority. You will receive a detailed resolution within "
            "7 working days as per our TAT commitment. We thank you for your "
            "patience and apologize for the inconvenience."
        ),
    },

    # ── Fraud / Unauthorized Transaction ─────────────────────────────────────
    {
        "category": "UNAUTHORIZED_TRANSACTION_FRAUD",
        "tier_level": 4,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding unauthorized "
            "fraudulent transactions on your account. This matter has been escalated "
            "to our Head Office Fraud Management team as per RBI mandate. Your "
            "account has been secured immediately. A provisional credit will be "
            "applied within 10 working days as per RBI limiting liability guidelines. "
            "A police complaint reference is required — please file an FIR at your "
            "nearest police station and share the reference with us. Our team will "
            "contact you within 48 hours."
        ),
    },

    # ── NEFT / RTGS / IMPS ────────────────────────────────────────────────────
    {
        "category": "NEFT",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the NEFT "
            "transaction where the amount was debited but not credited to the "
            "beneficiary. As per RBI NEFT guidelines, failed transactions must "
            "be reversed within 2 hours of the settlement cycle. The amount of "
            "Rs [AMOUNT] has been reversed to your account. If you wish to "
            "reattempt the transfer, please verify the beneficiary account details "
            "before initiating. We apologize for the inconvenience."
        ),
    },
    {
        "category": "IMPS",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have investigated your IMPS transaction failure. "
            "The transaction failed due to a temporary technical issue at the "
            "beneficiary bank. Your amount has been auto-reversed to your account "
            "within the RBI-mandated TAT. We have also waived the transaction fee "
            "as a goodwill gesture. Please retry the transaction after 30 minutes. "
            "We apologize for the inconvenience caused."
        ),
    },

    # ── Fixed Deposit ─────────────────────────────────────────────────────────
    {
        "category": "Fixed Deposit",
        "tier_level": 1,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding premature "
            "closure of your Fixed Deposit without consent. This was done in "
            "error and we sincerely apologize. Your FD has been reinstated at "
            "the original rate of interest with retrospective effect. The interest "
            "differential for the period has been credited to your savings account. "
            "We have placed a system flag to prevent any future unauthorized FD "
            "operations on your account."
        ),
    },

    # ── Insurance ─────────────────────────────────────────────────────────────
    {
        "category": "Insurance",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we have reviewed your complaint regarding the insurance "
            "policy mis-sold at our branch. As per IRDAI and RBI guidelines on "
            "bancassurance, insurance products must be sold with full disclosure "
            "and customer consent. We have initiated a policy cancellation request "
            "on your behalf and the premium paid will be refunded within 15 working "
            "days. We have also reported this to our compliance team for review "
            "of the sales process at the concerned branch."
        ),
    },

    # ── Education Loan ────────────────────────────────────────────────────────
    {
        "category": "Education Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "education loan disbursement. We understand the urgency given academic "
            "deadlines. After reviewing your file, we have identified the pending "
            "document and request you submit it at the earliest. Upon receipt, "
            "disbursement will be processed within 3 working days on priority. "
            "We apologize for the delay and have escalated your case to the "
            "Zonal Education Loan desk for expedited processing."
        ),
    },

    # ── Gold Loan ─────────────────────────────────────────────────────────────
    {
        "category": "Gold Loan",
        "tier_level": 2,
        "quality_score": 1.0,
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the auctioning "
            "of your gold without adequate notice. As per RBI guidelines, a minimum "
            "notice period must be provided before auction. We have halted the "
            "auction process immediately. Your gold ornaments are safe in our "
            "custody. Please visit the branch within 7 days to discuss a repayment "
            "arrangement. We apologize for the distress caused by this process."
        ),
    },
]


def generate_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model      = settings.openai_embedding_model,
        input      = text,
        dimensions = settings.openai_embedding_dimension,
    )
    return response.data[0].embedding


def seed():
    print(f"Seeding {len(SEED_DATA)} resolutions into knowledge_base...")
    print(f"Model: {settings.openai_embedding_model} ({settings.openai_embedding_dimension} dims)\n")

    success = 0
    failed  = 0

    for i, item in enumerate(SEED_DATA, 1):
        try:
            print(f"[{i:02d}/{len(SEED_DATA)}] {item['category'][:35]:<35} tier={item['tier_level']} ...", end=" ")
            embedding = generate_embedding(item["resolution_text"])

            supabase.table("knowledge_base").insert({
                "resolution_text": item["resolution_text"],
                "category":        item["category"],
                "source":          "seed",
                "quality_score":   item["quality_score"],
                "embedding":       embedding,
                "tier_level":      item["tier_level"],
                "tier_scope":      item.get("tier_scope"),
                "verified":        True,
            }).execute()

            success += 1
            print("OK")

        except Exception as e:
            failed += 1
            print(f"FAILED: {e}")

    print(f"\nDone: {success} inserted, {failed} failed.")
    print(f"Knowledge base now has {success} verified resolution templates.")
    print("\nCategories covered:")
    seen = {}
    for item in SEED_DATA:
        seen.setdefault(item["category"], 0)
        seen[item["category"]] += 1
    for cat, count in sorted(seen.items()):
        print(f"  {cat:<40} {count} entry/entries")


if __name__ == "__main__":
    seed()
