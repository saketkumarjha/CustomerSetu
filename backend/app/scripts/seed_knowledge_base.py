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

    # ══════════════════════════════════════════════════════════════════════════
    # COVERAGE GAP FILL — additional entries to reach ≥3 per category
    # ══════════════════════════════════════════════════════════════════════════

    # ── ATM (gap fill — 3rd entry) ────────────────────────────────────────────
    {
        "category": "ATM",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "ATM Card Swallowed",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding your debit card "
            "being retained by the ATM. This typically occurs when the card is not "
            "retrieved within the stipulated time or due to a card reader malfunction. "
            "We have raised a retrieval request with the ATM custodian. If the card "
            "cannot be retrieved safely, a replacement card will be dispatched to "
            "your registered address within 5 working days at no charge. Your "
            "existing card has been hotlisted to prevent misuse. We apologize for "
            "the inconvenience."
        ),
    },

    # ── Debit Card (gap fill — 3rd entry) ────────────────────────────────────
    {
        "category": "Debit Card",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "International Transaction Declined",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the decline of "
            "your debit card for international transactions. As per RBI guidelines, "
            "international usage on debit cards is disabled by default for security. "
            "You can enable international transactions via our mobile banking app "
            "under Card Controls, or by visiting your nearest branch. The feature "
            "can be activated for a specific duration and geography. We apologize "
            "for the inconvenience caused during your travel."
        ),
    },

    # ── Credit Card (gap fill — 3rd entry) ───────────────────────────────────
    {
        "category": "Credit Card",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Reward Points Not Credited",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding non-credit of "
            "reward points on your credit card transactions. After investigation, "
            "we confirm the points for transactions dated [DATE] were not processed "
            "due to a system reconciliation delay. The pending reward points of "
            "[POINTS] have been credited to your account with immediate effect. "
            "Your updated reward balance is now visible on the mobile app and "
            "internet banking portal. We apologize for the delay."
        ),
    },

    # ── Home Loan (gap fill — 3rd entry) ─────────────────────────────────────
    {
        "category": "Home Loan",
        "tier_level": 3,
        "quality_score": 0.95,
        "issue_type": "NOC Not Issued After Closure",
        "resolution_text": (
            "Dear Customer, we sincerely apologize for the delay in issuing your "
            "No Objection Certificate (NOC) after home loan closure. As per RBI "
            "Responsible Lending Conduct Directions 2023, the NOC and original "
            "property documents must be returned within 30 days of final repayment. "
            "Your NOC has been prepared and will be dispatched via registered post "
            "within 3 working days. The original title deeds will follow separately "
            "under insured courier. We have also updated CERSAI records to release "
            "the charge on your property. We regret the delay."
        ),
    },

    # ── Business Loan (gap fill — 3rd entry) ─────────────────────────────────
    {
        "category": "Business Loan",
        "tier_level": 3,
        "quality_score": 0.95,
        "issue_type": "Collateral Release Delayed",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "release of collateral securities post business loan closure. As per "
            "RBI guidelines, collateral must be released within 30 days of full "
            "repayment. We have escalated this to our Regional Credit Operations "
            "team. Your collateral documents including the original property papers "
            "and hypothecation release letter will be handed over at your home "
            "branch within 7 working days. We apologize for the delay and the "
            "inconvenience caused to your business operations."
        ),
    },

    # ── Savings Account (gap fill — 3rd entry) ───────────────────────────────
    {
        "category": "Savings Account",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Account Frozen Without Notice",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the freezing "
            "of your savings account without prior notice. As per RBI KYC Master "
            "Direction 2016, customers must be notified before any account "
            "restrictions are imposed. We apologize for not following this "
            "procedure. After reviewing your account, we confirm the freeze was "
            "applied in error. Your account has been unfrozen with immediate "
            "effect and is fully operational. We have also waived any charges "
            "incurred due to the erroneous freeze. We regret the inconvenience."
        ),
    },

    # ── Current Account (gap fill — 2nd and 3rd entries) ─────────────────────
    {
        "category": "Current Account",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Cheque Book Not Delivered",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding non-delivery "
            "of your current account cheque book. Our records confirm the cheque "
            "book was dispatched on [DATE] via speed post. We have raised a "
            "complaint with the postal department and simultaneously issued a "
            "fresh cheque book which will be delivered to your registered address "
            "within 5 working days. The previous cheque book series has been "
            "cancelled to prevent misuse. We apologize for the inconvenience "
            "caused to your business operations."
        ),
    },
    {
        "category": "Current Account",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Overdraft Limit Reduced Without Notice",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the reduction "
            "of your current account overdraft limit without prior intimation. "
            "As per RBI Fair Practices Code, any reduction in sanctioned limits "
            "must be communicated in advance. We have reviewed your account and "
            "confirm the limit was reduced due to an automated credit review. "
            "Your overdraft limit has been restored to the original sanctioned "
            "amount pending a formal review. Our relationship manager will contact "
            "you within 48 hours to discuss the renewal. We apologize for the "
            "disruption to your business."
        ),
    },

    # ── Internet Banking (gap fill — 3rd entry) ───────────────────────────────
    {
        "category": "Internet Banking",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "OTP Not Received",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding non-receipt "
            "of OTP for internet banking transactions. This may occur due to "
            "network congestion or your mobile number not being updated in our "
            "records. We have verified your registered mobile number and confirmed "
            "it is correct. Our technical team has refreshed the OTP delivery "
            "service for your account. Please retry after 15 minutes. If the "
            "issue persists, you may use our TOTP-based authenticator app as an "
            "alternative. We apologize for the inconvenience."
        ),
    },

    # ── UPI (3rd entry — higher tier scenario) ────────────────────────────────
    {
        "category": "UPI",
        "tier_level": 3,
        "quality_score": 0.95,
        "issue_type": "UPI Fraud — Phishing",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding a fraudulent "
            "UPI transaction initiated through a phishing link. This matter has "
            "been escalated to our Regional Fraud Management team. Your UPI ID "
            "has been suspended to prevent further misuse. As per RBI guidelines "
            "on limiting liability for third-party fraud, a provisional credit "
            "will be applied within 10 working days subject to investigation. "
            "Please file a cybercrime complaint at cybercrime.gov.in and share "
            "the reference number with us. Do not share OTP or UPI PIN with "
            "anyone. We will contact you within 24 hours."
        ),
    },

    # ── Personal Loan (3rd entry — higher tier) ───────────────────────────────
    {
        "category": "Personal Loan",
        "tier_level": 3,
        "quality_score": 0.95,
        "issue_type": "Recovery Agent Harassment",
        "resolution_text": (
            "Dear Customer, we take your complaint regarding recovery agent "
            "harassment with utmost seriousness. As per RBI guidelines on Fair "
            "Practices Code for Lenders, recovery agents are strictly prohibited "
            "from contacting borrowers before 8 AM or after 7 PM, using abusive "
            "language, or contacting family members. We have immediately suspended "
            "the concerned recovery agent pending investigation. A formal complaint "
            "has been filed with our compliance team. This matter has been escalated "
            "to our Regional Nodal Officer. We will contact you within 24 hours "
            "with a resolution. We sincerely apologize for this unacceptable conduct."
        ),
    },

    # ── Forex ─────────────────────────────────────────────────────────────────
    {
        "category": "Forex",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Wrong Exchange Rate Applied",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the incorrect "
            "exchange rate applied to your foreign currency transaction. After "
            "reviewing the transaction dated [DATE], we confirm the rate applied "
            "deviated from the card rate published on our website at the time of "
            "transaction. The difference of Rs [AMOUNT] has been credited to your "
            "account. Going forward, you can check the live forex rates on our "
            "website or mobile app before initiating international transactions. "
            "We apologize for the discrepancy."
        ),
    },
    {
        "category": "Forex",
        "tier_level": 2,
        "quality_score": 0.90,
        "issue_type": "Forex Card Not Loaded",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "loading your forex travel card. The loading request placed on [DATE] "
            "was held due to a pending FEMA compliance check. The check has been "
            "completed and your card has been loaded with the requested amount of "
            "[CURRENCY] [AMOUNT]. The card is now active and ready for use. "
            "Please check the balance via our mobile app or at any ATM abroad. "
            "We apologize for the delay and the inconvenience caused to your "
            "travel plans."
        ),
    },

    # ── Investment / Mutual Fund ──────────────────────────────────────────────
    {
        "category": "Investment / Mutual Fund",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "SIP Not Executed",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the non-execution "
            "of your SIP instalment for [MONTH]. After investigation, we confirm "
            "the SIP debit failed due to insufficient balance in your linked savings "
            "account on the due date. As per SEBI guidelines, missed SIP instalments "
            "cannot be backdated. We recommend maintaining a minimum balance of "
            "1.5x your SIP amount on the debit date to avoid future failures. "
            "Your SIP mandate remains active and will execute on the next due date. "
            "We apologize for the inconvenience."
        ),
    },
    {
        "category": "Investment / Mutual Fund",
        "tier_level": 2,
        "quality_score": 0.90,
        "issue_type": "Redemption Amount Not Credited",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "credit of mutual fund redemption proceeds. As per SEBI regulations, "
            "redemption proceeds for equity funds must be credited within T+3 "
            "working days and for debt funds within T+2 working days. We have "
            "traced your redemption request and confirm the proceeds of Rs [AMOUNT] "
            "were delayed due to a bank account validation mismatch. The amount "
            "has been credited to your registered bank account. We apologize for "
            "the delay."
        ),
    },

    # ── Vehicle Loan ──────────────────────────────────────────────────────────
    {
        "category": "Vehicle Loan",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "RC Book Hypothecation Not Removed",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "removal of hypothecation from your vehicle RC book after loan closure. "
            "As per RBI Responsible Lending Conduct Directions 2023, the NOC for "
            "hypothecation removal must be issued within 30 days of final repayment. "
            "Your NOC has been prepared and will be dispatched within 3 working days. "
            "You may submit this NOC to your Regional Transport Office (RTO) to "
            "update the RC book. We have also updated VAHAN records where applicable. "
            "We apologize for the delay."
        ),
    },
    {
        "category": "Vehicle Loan",
        "tier_level": 1,
        "quality_score": 0.90,
        "issue_type": "EMI Deducted Twice",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding duplicate EMI "
            "deduction for your vehicle loan. Our investigation confirms two EMI "
            "debits were processed on [DATE] due to a technical error in the "
            "auto-debit system. The excess debit of Rs [AMOUNT] has been reversed "
            "to your savings account with value dating to the original debit date "
            "to ensure no loss of interest. We have also raised a technical ticket "
            "to prevent recurrence. We sincerely apologize for the inconvenience."
        ),
    },

    # ── Fixed Deposit (2nd and 3rd entries) ───────────────────────────────────
    {
        "category": "Fixed Deposit",
        "tier_level": 1,
        "quality_score": 0.95,
        "issue_type": "FD Interest Rate Discrepancy",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the interest "
            "rate applied to your Fixed Deposit. After reviewing your FD account, "
            "we confirm the rate applied was lower than the rate advertised on the "
            "date of booking. The differential interest of Rs [AMOUNT] has been "
            "credited to your savings account. Your FD has been updated to reflect "
            "the correct rate for the remaining tenure. A revised FD receipt will "
            "be sent to your registered email within 2 working days. We apologize "
            "for the discrepancy."
        ),
    },
    {
        "category": "Fixed Deposit",
        "tier_level": 2,
        "quality_score": 0.90,
        "issue_type": "TDS Deducted Despite Form 15G Submission",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding TDS deduction "
            "on your Fixed Deposit interest despite submission of Form 15G. Our "
            "records confirm the form was submitted but not processed before the "
            "interest credit date due to a system delay. We have raised a TDS "
            "correction request with the Income Tax department. A TDS certificate "
            "in Form 16A will be issued for the deducted amount, which you can "
            "claim as a refund while filing your ITR. We apologize for the "
            "inconvenience and have updated your records to prevent recurrence."
        ),
    },

    # ── Insurance (2nd and 3rd entries) ──────────────────────────────────────
    {
        "category": "Insurance",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Claim Rejected",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the rejection "
            "of your insurance claim. After reviewing the rejection reason provided "
            "by the insurer, we have escalated this to our bancassurance grievance "
            "cell. As per IRDAI guidelines, insurers must provide a detailed written "
            "reason for claim rejection. We have requested the insurer to reconsider "
            "your claim and provide a detailed explanation within 15 days. If the "
            "rejection is upheld, you may approach the Insurance Ombudsman. We will "
            "assist you through this process. We apologize for the distress caused."
        ),
    },
    {
        "category": "Insurance",
        "tier_level": 3,
        "quality_score": 0.90,
        "issue_type": "Premium Deducted Without Consent",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding insurance "
            "premium deduction without your explicit consent. This is a serious "
            "violation of IRDAI and RBI bancassurance guidelines which mandate "
            "written consent before any premium deduction. This matter has been "
            "escalated to our Regional Compliance Officer. The premium amount of "
            "Rs [AMOUNT] has been refunded to your account with immediate effect. "
            "The policy has been cancelled and a cancellation confirmation will "
            "be sent within 7 working days. We have initiated disciplinary action "
            "against the concerned staff. We sincerely apologize."
        ),
    },

    # ── Locker (2nd and 3rd entries) ──────────────────────────────────────────
    {
        "category": "Locker",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Locker Not Allotted Despite Payment",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding non-allotment "
            "of a locker despite payment of the annual rent. As per RBI revised "
            "locker guidelines effective January 2023, banks must maintain a "
            "waitlist and allot lockers in order of registration. We confirm your "
            "name is on the waitlist at [BRANCH] branch. A locker has now become "
            "available and has been allotted to you. Please visit the branch with "
            "your ID proof to complete the locker agreement formalities. The rent "
            "paid will be adjusted against the current year. We apologize for the "
            "wait."
        ),
    },
    {
        "category": "Locker",
        "tier_level": 3,
        "quality_score": 0.90,
        "issue_type": "Locker Broken Into / Contents Missing",
        "resolution_text": (
            "Dear Customer, we acknowledge your extremely serious complaint "
            "regarding the alleged breach of your safe deposit locker. As per "
            "RBI revised locker guidelines 2023, banks are liable for losses "
            "due to their negligence up to 100 times the annual locker rent. "
            "This matter has been escalated to our Regional Head and a formal "
            "investigation has been initiated. The branch has been instructed to "
            "preserve all CCTV footage and access logs. A police complaint has "
            "been filed. Our Regional Nodal Officer will contact you within 24 "
            "hours. We take this matter with the utmost seriousness and sincerely "
            "apologize for the distress caused."
        ),
    },

    # ── KYC (3rd entry) ───────────────────────────────────────────────────────
    {
        "category": "KYC",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Video KYC Failed Repeatedly",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding repeated "
            "failures during Video KYC. This may occur due to poor network "
            "connectivity, document quality, or system issues. We have reviewed "
            "your Video KYC attempts and identified a technical issue on our end. "
            "Our team has reset your Video KYC session. Please retry using a "
            "stable internet connection in a well-lit environment with your "
            "original Aadhaar and PAN ready. Alternatively, you may complete "
            "your KYC by visiting your nearest branch. We apologize for the "
            "repeated inconvenience."
        ),
    },

    # ── Cheque (3rd entry) ────────────────────────────────────────────────────
    {
        "category": "Cheque",
        "tier_level": 2,
        "quality_score": 0.90,
        "issue_type": "Cheque Truncation System Error",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the delay in "
            "clearing of your cheque under the Cheque Truncation System (CTS). "
            "The cheque presented on [DATE] was held due to an image quality "
            "rejection in the CTS grid. We have re-presented the cheque with "
            "corrected image parameters. The proceeds of Rs [AMOUNT] will be "
            "credited to your account within 2 working days. We have also applied "
            "delayed credit interest for the period of delay. We apologize for "
            "the inconvenience caused."
        ),
    },

    # ── General Banking — Tier 3 and 5 entries ────────────────────────────────
    {
        "category": "General Banking",
        "tier_level": 3,
        "quality_score": 0.95,
        "issue_type": "Repeated Unresolved Complaint",
        "resolution_text": (
            "Dear Customer, we sincerely apologize that your complaint has not "
            "been resolved despite multiple follow-ups. This is unacceptable and "
            "does not reflect our service standards. Your complaint has been "
            "escalated to our Regional Grievance Officer who will personally "
            "oversee the resolution. You will receive a call from our Regional "
            "team within 24 hours with a definitive resolution timeline. As a "
            "goodwill gesture, we have waived all charges related to this complaint. "
            "We assure you this will be resolved within 5 working days. We deeply "
            "regret the repeated inconvenience."
        ),
    },
    {
        "category": "General Banking",
        "tier_level": 5,
        "quality_score": 1.0,
        "issue_type": "RBI Ombudsman Escalation",
        "resolution_text": (
            "Dear Customer, we acknowledge that your complaint has been escalated "
            "to the RBI Banking Ombudsman. We take this matter with the highest "
            "priority. Our Nodal Officer has been assigned to handle your case "
            "directly and will submit a detailed response to the Ombudsman within "
            "the stipulated timeframe. We have reviewed your complaint history and "
            "are committed to providing a fair and final resolution. Our Nodal "
            "Officer will contact you within 24 hours. We sincerely apologize for "
            "the experience that led to this escalation and assure you of our "
            "full cooperation with the Ombudsman process."
        ),
    },

    # ── NEFT (2nd entry) ──────────────────────────────────────────────────────
    {
        "category": "NEFT",
        "tier_level": 2,
        "quality_score": 0.95,
        "issue_type": "Wrong Account Credited",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding NEFT credit "
            "to a wrong account. As per RBI guidelines, if a wrong credit occurs "
            "due to beneficiary details provided by the remitter, the bank is not "
            "liable but must make best efforts to recover the funds. We have "
            "immediately placed a lien on the beneficiary account and initiated "
            "a recall request. If the beneficiary cooperates, the amount will be "
            "reversed within 7 working days. If not, you may need to pursue "
            "legal recourse. We will keep you updated on the recovery status. "
            "We advise double-checking beneficiary details before future transfers."
        ),
    },

    # ── Mobile Banking (2nd and 3rd entries) ──────────────────────────────────
    {
        "category": "Mobile Banking",
        "tier_level": 1,
        "quality_score": 0.95,
        "issue_type": "Mobile Banking Registration Failed",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding failure to "
            "register for mobile banking. This may occur if your mobile number "
            "is not updated in our records or if there is a mismatch in your "
            "account details. We have verified your records and updated your "
            "registered mobile number. Please retry the registration process "
            "using the OTP that will be sent to your updated number. If the "
            "issue persists, please visit your nearest branch with your Aadhaar "
            "and account passbook for assisted registration. We apologize for "
            "the inconvenience."
        ),
    },
    {
        "category": "Mobile Banking",
        "tier_level": 2,
        "quality_score": 0.90,
        "issue_type": "Fund Transfer Limit Not Increased",
        "resolution_text": (
            "Dear Customer, we acknowledge your complaint regarding the rejection "
            "of your request to increase the mobile banking fund transfer limit. "
            "As per RBI guidelines, enhanced transaction limits require additional "
            "authentication and risk assessment. After reviewing your account "
            "profile and transaction history, we have approved an increase in your "
            "daily transfer limit to Rs [AMOUNT]. The revised limit will be active "
            "within 4 hours. For limits above Rs 5 lakh per day, a branch visit "
            "with ID proof is required. We apologize for the delay in processing "
            "your request."
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
