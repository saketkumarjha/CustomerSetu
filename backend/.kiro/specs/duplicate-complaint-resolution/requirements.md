# Requirements Document

## Introduction

When the duplicate detection agent (`duplicate_agent.py`) marks an incoming complaint as a duplicate of an existing complaint, the system today ends the pipeline immediately — no further action is taken for the customer who submitted the duplicate. This feature closes that gap.

The goal is: if the original complaint has already been fully resolved and a final response has been sent to the original customer, that same resolution should be automatically forwarded to the customer who submitted the duplicate complaint — but only after an LLM-based verification agent confirms the two complaints describe the same underlying problem and that the existing resolution genuinely applies.

If the original complaint is still in-flight (not yet resolved, or not yet responded to), or if the verification agent determines the resolution does not apply, the duplicate complaint is queued for human review rather than being silently dropped.

---

## Glossary

- **Duplicate_Complaint**: A complaint whose `is_duplicate` flag is `true` and whose `duplicate_of` field references the ID of the Original_Complaint.
- **Original_Complaint**: The earlier complaint record that the Duplicate_Complaint was matched against during embedding-based similarity search.
- **Resolution_Forwarder**: The new service module responsible for orchestrating the lookup, verification, and forwarding flow described in this document.
- **Verification_Agent**: An LLM-based agent (GPT-4o) that determines whether the resolution of the Original_Complaint genuinely applies to the Duplicate_Complaint.
- **Final_Response**: The `final_response_text` stored on a complaint record, set when `response_sent_at` is non-null and `pipeline_status` is `complete`.
- **Pipeline**: The LangGraph multi-agent orchestration defined in `graph.py`.
- **Supervisor**: The LangGraph `StateGraph` runner that controls agent execution order and branching.
- **notification_log**: The Supabase table that records every customer-facing notification event.
- **agent_decisions**: The Supabase table that records every agent decision for audit purposes.
- **PII**: Personally Identifiable Information, masked by the PII agent before any text is passed to LLM agents.

---

## Requirements

### Requirement 1: Resolution Status Lookup

**User Story:** As a bank operations system, I want to look up the most recent resolution status of the Original_Complaint after a duplicate is detected, so that the system knows whether a final response is already available to forward.

#### Acceptance Criteria

1. WHEN the Duplicate_Complaint is identified by the duplicate detection agent, THE Resolution_Forwarder SHALL query the `complaints` table for the Original_Complaint record using the `duplicate_of` complaint ID.
2. THE Resolution_Forwarder SHALL retrieve the following fields from the Original_Complaint: `status`, `pipeline_status`, `final_response_text`, `response_sent_at`, `response_channel`, `masked_text`, `category`, `sentiment`, `draft_response`.
3. IF the Original_Complaint record does not exist in the `complaints` table, THEN THE Resolution_Forwarder SHALL mark the Duplicate_Complaint `pipeline_status` as `pending_human_review` and halt the forwarding flow.
4. IF the Original_Complaint `response_sent_at` is null or `final_response_text` is null, THEN THE Resolution_Forwarder SHALL mark the Duplicate_Complaint `pipeline_status` as `pending_human_review` and halt the forwarding flow.
5. THE Resolution_Forwarder SHALL complete the status lookup within 3 seconds under normal Supabase latency conditions.

---

### Requirement 2: Resolution Applicability Verification

**User Story:** As a bank operations system, I want an LLM agent to verify that the resolved Original_Complaint actually addresses the same problem as the Duplicate_Complaint before forwarding the resolution, so that customers do not receive irrelevant or incorrect responses.

#### Acceptance Criteria

1. WHEN the Original_Complaint has a non-null `final_response_text` and non-null `response_sent_at`, THE Verification_Agent SHALL compare the `masked_text` of the Duplicate_Complaint with the `masked_text` of the Original_Complaint.
2. THE Verification_Agent SHALL determine whether the resolution described in `final_response_text` of the Original_Complaint genuinely addresses the issue described in the Duplicate_Complaint's `masked_text`.
3. THE Verification_Agent SHALL return a structured JSON decision containing: `is_applicable` (bool), `confidence` (float 0.0–1.0), `reasoning` (string), and `verification_summary` (string, ≤ 200 characters).
4. WHERE the `is_applicable` result is `true` and `confidence` is greater than or equal to 0.85, THE Resolution_Forwarder SHALL proceed to forward the resolution to the Duplicate_Complaint's customer.
5. IF the `is_applicable` result is `false`, THEN THE Resolution_Forwarder SHALL mark the Duplicate_Complaint `pipeline_status` as `pending_human_review` and record the Verification_Agent's `reasoning` in the `agent_decisions` table.
6. IF the Verification_Agent `confidence` is less than 0.85, THEN THE Resolution_Forwarder SHALL mark the Duplicate_Complaint `pipeline_status` as `pending_human_review` and record the low-confidence reasoning in the `agent_decisions` table.
7. THE Verification_Agent SHALL use the `masked_text` of both complaints (not `original_text`) so that PII differences between customers do not affect the applicability decision.
8. THE Verification_Agent SHALL complete its LLM call within 30 seconds; IF the call exceeds 30 seconds, THEN THE Resolution_Forwarder SHALL treat the verification as failed and route to `pending_human_review`.

---

### Requirement 3: Resolution Forwarding

**User Story:** As a customer who submitted a duplicate complaint, I want to receive the same resolution that was already sent for my issue, so that I do not have to wait for the same problem to be re-investigated.

#### Acceptance Criteria

1. WHEN the Verification_Agent confirms `is_applicable` is `true` with `confidence` >= 0.85, THE Resolution_Forwarder SHALL send the `final_response_text` of the Original_Complaint to the customer of the Duplicate_Complaint via the Duplicate_Complaint's `response_channel`.
2. THE Resolution_Forwarder SHALL update the Duplicate_Complaint record in the `complaints` table with: `status` = `resolved`, `pipeline_status` = `duplicate_resolved`, `final_response_text` = the forwarded text, `response_sent_at` = the current UTC timestamp, `response_channel` = the Duplicate_Complaint's channel.
3. THE Resolution_Forwarder SHALL insert a row into `notification_log` recording the forwarding event with fields: `complaint_id` (Duplicate_Complaint ID), `channel`, `status` = `sent`, `sent_at`, `tier_level` = 0, `confidence` = Verification_Agent confidence.
4. THE Resolution_Forwarder SHALL insert a row into `agent_decisions` recording the Verification_Agent decision for audit, including `verification_summary` and `confidence`.
5. WHERE the Duplicate_Complaint `response_channel` is `email`, THE Resolution_Forwarder SHALL send the response via the existing SMTP email service.
6. WHERE the Duplicate_Complaint `response_channel` is `web`, THE Resolution_Forwarder SHALL extract the customer email from `original_text` and send via the existing SMTP email service.
7. WHERE the Duplicate_Complaint `response_channel` is `whatsapp` or `sms`, THE Resolution_Forwarder SHALL log the forwarding event to the console (gateway simulation) and mark `response_sent_at` on the record.
8. IF the send operation fails due to an SMTP or gateway error, THEN THE Resolution_Forwarder SHALL mark the Duplicate_Complaint `pipeline_status` as `pending_human_review` and log the error, so no customer notification is silently lost.

---

### Requirement 4: Pipeline Integration

**User Story:** As a system architect, I want the resolution forwarding flow to be triggered from within the existing LangGraph pipeline graph, so that no duplicate complaint falls through without a defined outcome.

#### Acceptance Criteria

1. WHEN the `route_after_duplicate` conditional edge in `graph.py` evaluates `is_duplicate` as `true`, THE Pipeline SHALL invoke the Resolution_Forwarder before terminating the pipeline for the Duplicate_Complaint.
2. THE Pipeline SHALL update the Duplicate_Complaint `complaints` record with `is_duplicate` = `true` and `duplicate_of` = the Original_Complaint ID before invoking the Resolution_Forwarder.
3. THE Pipeline SHALL store the Resolution_Forwarder's outcome in the `PipelineState` under a key `duplicate_resolution_result` of type `dict`.
4. THE Pipeline SHALL emit SSE events via `event_bus` at the start and completion of the Resolution_Forwarder invocation, using `agent_name` = `"Duplicate Resolution Forwarder"` and `agent_order` = 2.5.
5. THE Pipeline SHALL write the Resolution_Forwarder decision to the `agent_decisions` audit table via the existing `write_agent_decision` utility.
6. IF the Resolution_Forwarder raises an unhandled exception, THEN THE Pipeline SHALL catch the exception, mark the Duplicate_Complaint `pipeline_status` as `pending_human_review`, log the error, and terminate the pipeline gracefully without propagating the exception to the caller.

---

### Requirement 5: Human Review Fallback

**User Story:** As a human bank agent, I want duplicate complaints that cannot be automatically resolved to appear in the human review queue, so that no customer inquiry is silently dropped.

#### Acceptance Criteria

1. WHEN the Resolution_Forwarder sets `pipeline_status` to `pending_human_review` for any reason, THE Resolution_Forwarder SHALL insert a row into the `agent_queue` table with `complaint_id`, `queue_type` = `duplicate_unresolved`, `priority` derived from the Duplicate_Complaint's `sentiment` (Furious/Angry = high, others = normal), and `created_at` = current UTC timestamp.
2. THE Resolution_Forwarder SHALL record the reason for human escalation in the `agent_decisions` table so that the reviewing agent understands why automatic forwarding did not occur.
3. IF the `agent_queue` insert fails, THEN THE Resolution_Forwarder SHALL log the failure at ERROR level, so the failure is visible in monitoring; the Duplicate_Complaint `pipeline_status` SHALL remain `pending_human_review`.
4. THE Resolution_Forwarder SHALL set the Duplicate_Complaint `status` to `open` when routing to `pending_human_review`, so the complaint appears as actionable in the human agent dashboard.

---

### Requirement 6: Audit and Observability

**User Story:** As a compliance officer, I want every forwarding decision — successful or failed — to be recorded in the audit trail, so that the bank can demonstrate regulatory compliance for duplicate complaint handling.

#### Acceptance Criteria

1. THE Resolution_Forwarder SHALL record every execution in `agent_decisions` with: `complaint_id`, `agent_name` = `"Duplicate Resolution Forwarder"`, `decision` (outcome summary string), `confidence` (Verification_Agent confidence or 0.0 for lookup failures), `reasoning` (full reasoning chain), and `created_at`.
2. THE Resolution_Forwarder SHALL include in `reasoning` the Original_Complaint ID, the similarity score from the duplicate detection step, the Verification_Agent `verification_summary`, and the final outcome.
3. WHEN the Resolution_Forwarder forwards a resolution, THE Resolution_Forwarder SHALL log at INFO level: the Duplicate_Complaint ID, the Original_Complaint ID, the `response_channel`, and the Verification_Agent confidence.
4. WHEN the Resolution_Forwarder routes to human review, THE Resolution_Forwarder SHALL log at WARNING level: the Duplicate_Complaint ID, the Original_Complaint ID, and the reason for human escalation.
5. THE Resolution_Forwarder SHALL not log the `original_text` or `final_response_text` content at DEBUG or INFO level, to prevent PII leakage into log streams.
