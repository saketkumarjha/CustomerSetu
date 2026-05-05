"""
RBI Category definitions — Enum and metadata.

Single source of truth for all RBI-regulated complaint categories.
Used by:
  - Compliance Agent (to classify complaints)
  - Risk Router (to apply override rules)
  - RBI Reporting endpoint (to filter reportable complaints)
  - TAT rules (to assign deadlines)
"""

from enum import Enum


class RBICategory(str, Enum):
    """All 13 RBI-regulated complaint categories + NOT_APPLICABLE."""

    # Digital Banking & Payments
    UNAUTHORIZED_TRANSACTION_FRAUD = "UNAUTHORIZED_TRANSACTION_FRAUD"
    FAILED_TRANSACTION_TAT_BREACH = "FAILED_TRANSACTION_TAT_BREACH"
    UPI_BBPS_SETTLEMENT_ISSUE = "UPI_BBPS_SETTLEMENT_ISSUE"

    # Loans & Advances
    RECOVERY_AGENT_HARASSMENT = "RECOVERY_AGENT_HARASSMENT"
    DELAY_IN_PROPERTY_DOC_RELEASE = "DELAY_IN_PROPERTY_DOC_RELEASE"
    UNFAIR_LOAN_CHARGES_OR_RATES = "UNFAIR_LOAN_CHARGES_OR_RATES"

    # Cards
    DELAY_IN_CARD_CLOSURE = "DELAY_IN_CARD_CLOSURE"
    UNSOLICITED_CARD_ISSUANCE = "UNSOLICITED_CARD_ISSUANCE"
    HIDDEN_CARD_CHARGES = "HIDDEN_CARD_CHARGES"

    # Customer Service & Operations
    CREDIT_BUREAU_MISREPORTING = "CREDIT_BUREAU_MISREPORTING"
    KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE = "KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE"
    MIS_SELLING_OF_PRODUCTS = "MIS_SELLING_OF_PRODUCTS"
    NON_ADHERENCE_TO_FPC = "NON_ADHERENCE_TO_FPC"

    # Not regulated
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Categories that ALWAYS force human review — no exceptions
# RBI mandates human handling for these — AI auto-respond is prohibited
SUPERVISOR_OVERRIDE_ALWAYS_HUMAN = {
    RBICategory.RECOVERY_AGENT_HARASSMENT,
    RBICategory.UNAUTHORIZED_TRANSACTION_FRAUD,
    RBICategory.UNSOLICITED_CARD_ISSUANCE,
    RBICategory.MIS_SELLING_OF_PRODUCTS,
}

# Categories that are RBI-reportable
RBI_REPORTABLE_CATEGORIES = {
    RBICategory.UNAUTHORIZED_TRANSACTION_FRAUD,
    RBICategory.FAILED_TRANSACTION_TAT_BREACH,
    RBICategory.UPI_BBPS_SETTLEMENT_ISSUE,
    RBICategory.RECOVERY_AGENT_HARASSMENT,
    RBICategory.DELAY_IN_PROPERTY_DOC_RELEASE,
    RBICategory.UNFAIR_LOAN_CHARGES_OR_RATES,
    RBICategory.DELAY_IN_CARD_CLOSURE,
    RBICategory.UNSOLICITED_CARD_ISSUANCE,
    RBICategory.HIDDEN_CARD_CHARGES,
    RBICategory.CREDIT_BUREAU_MISREPORTING,
    RBICategory.KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE,
    RBICategory.MIS_SELLING_OF_PRODUCTS,
}

# Human-readable labels for XAI display
CATEGORY_LABELS = {
    RBICategory.UNAUTHORIZED_TRANSACTION_FRAUD: "Unauthorized Transaction / Fraud",
    RBICategory.FAILED_TRANSACTION_TAT_BREACH: "Failed Transaction TAT Breach",
    RBICategory.UPI_BBPS_SETTLEMENT_ISSUE: "UPI/BBPS Settlement Issue",
    RBICategory.RECOVERY_AGENT_HARASSMENT: "Recovery Agent Harassment",
    RBICategory.DELAY_IN_PROPERTY_DOC_RELEASE: "Delay in Property Document Release",
    RBICategory.UNFAIR_LOAN_CHARGES_OR_RATES: "Unfair Loan Charges or Rates",
    RBICategory.DELAY_IN_CARD_CLOSURE: "Delay in Card Closure",
    RBICategory.UNSOLICITED_CARD_ISSUANCE: "Unsolicited Card Issuance",
    RBICategory.HIDDEN_CARD_CHARGES: "Hidden Card Charges",
    RBICategory.CREDIT_BUREAU_MISREPORTING: "Credit Bureau Misreporting",
    RBICategory.KYC_ACCOUNT_FREEZE_WITHOUT_NOTICE: "KYC Account Freeze Without Notice",
    RBICategory.MIS_SELLING_OF_PRODUCTS: "Mis-selling of Products",
    RBICategory.NON_ADHERENCE_TO_FPC: "Non-Adherence to Fair Practices Code",
    RBICategory.NOT_APPLICABLE: "Not Applicable",
}