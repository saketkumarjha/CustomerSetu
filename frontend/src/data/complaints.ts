import type { Complaint } from '../types'

export const COMPLAINTS: Complaint[] = [
  {
    id: 'CMP-2026-001',
    customer: 'Rajesh Kumar',
    accountNo: 'SB****4521',
    phone: '+91 98765 43210',
    channel: 'Email',
    category: 'Credit Card',
    type: 'Unauthorized Transaction',
    severity: 'Critical',
    sentiment: 'Angry',
    sentimentScore: 18,
    status: 'Open',
    slaHours: 2,
    slaRemaining: '1h 23m',
    slaBreached: false,
    assignee: 'Priya Sharma',
    branch: 'Mumbai – Andheri West',
    date: '2026-03-20',
    time: '10:32 AM',
    description:
      'I noticed two unauthorized transactions of Rs.15,000 each on my credit card ending 4521 on March 19th. I did not make these purchases. Please investigate and refund immediately. This is very urgent.',
    history: [
      { time: '10:32 AM', actor: 'Customer', action: 'Complaint submitted via Email' },
      { time: '10:33 AM', actor: 'AI System', action: 'Auto-classified: Critical Fraud — confidence 97%' },
      { time: '10:34 AM', actor: 'AI System', action: 'Compliance flag raised — RBI fraud reporting required within 24h' },
      { time: '10:45 AM', actor: 'Priya Sharma', action: 'Complaint assigned, investigation initiated' },
    ],
    agentResult: {
      classification: { category: 'Credit Card', product: 'Credit Card Classic', severity: 'Critical', type: 'Fraud / Unauthorized Transaction', confidence: 97 },
      sentiment: { emotion: 'Angry', urgency: 95, score: 18, escalate: true, confidence: 94 },
      duplicate: { isDuplicate: false, similar: 0, confidence: 99 },
      compliance: { flagged: true, risk: 'HIGH', reason: 'RBI Fraud Reporting mandate — must report within 24h', confidence: 98 },
      resolution: `Dear Rajesh Kumar,

Thank you for bringing this to our attention. We sincerely apologize for this distressing experience.

We have immediately:
1. Blocked your Credit Card ending 4521 to prevent further transactions
2. Initiated a chargeback investigation for Rs.30,000 (2 x Rs.15,000)
3. Filed a Fraud Alert as per RBI guidelines (Ref: FRD-2026-0320-001)

A provisional credit will reflect within 3-5 working days, with final resolution within 45 days.

For queries, call our 24/7 Fraud Helpline: 1800-22-2244

Sincerely,
Union Bank of India — Fraud Resolution Team`,
    },
  },
  {
    id: 'CMP-2026-002',
    customer: 'Meera Patel',
    accountNo: 'SB****7832',
    phone: '+91 87654 32109',
    channel: 'Phone',
    category: 'Loans',
    type: 'Double EMI Deduction',
    severity: 'High',
    sentiment: 'Frustrated',
    sentimentScore: 35,
    status: 'In Progress',
    slaHours: 24,
    slaRemaining: '18h 45m',
    slaBreached: false,
    assignee: 'Arjun Mehta',
    branch: 'Ahmedabad – CG Road',
    date: '2026-03-20',
    time: '09:15 AM',
    description:
      'My home loan EMI of Rs.32,500 has been deducted twice from my savings account this month — once on March 1st and again on March 3rd. My account balance is now negative. Please refund the extra amount immediately.',
    history: [
      { time: '09:15 AM', actor: 'Customer', action: 'Complaint raised via Phone Call' },
      { time: '09:16 AM', actor: 'AI System', action: 'High priority — Loan EMI duplicate deduction classified' },
      { time: '09:30 AM', actor: 'Arjun Mehta', action: 'Coordinating with loan processing team' },
    ],
    agentResult: {
      classification: { category: 'Loans', product: 'Home Loan', severity: 'High', type: 'Double EMI Deduction / System Error', confidence: 95 },
      sentiment: { emotion: 'Frustrated', urgency: 80, score: 35, escalate: false, confidence: 91 },
      duplicate: { isDuplicate: false, similar: 2, confidence: 88 },
      compliance: { flagged: false, risk: 'LOW', reason: 'Standard complaint — no regulatory breach', confidence: 96 },
      resolution: `Dear Meera Patel,

We sincerely apologize for the inconvenience caused by the double EMI deduction.

This was identified as a technical error in our loan processing system. We will:
1. Refund Rs.32,500 (duplicate EMI) to your account within 2 working days
2. Waive all overdraft charges incurred due to this error
3. Ensure this cannot recur on your account

Complaint reference: LN-2026-0320-002

Sincerely,
Union Bank of India — Loan Services`,
    },
  },
  {
    id: 'CMP-2026-003',
    customer: 'Suresh Reddy',
    accountNo: 'SB****2910',
    phone: '+91 76543 21098',
    channel: 'Web Form',
    category: 'ATM / Cash',
    type: 'Cash Not Dispensed',
    severity: 'High',
    sentiment: 'Upset',
    sentimentScore: 38,
    status: 'Resolved',
    slaHours: 24,
    slaRemaining: 'Resolved',
    slaBreached: false,
    assignee: 'Kavitha Nair',
    branch: 'Hyderabad – Banjara Hills',
    date: '2026-03-19',
    time: '03:45 PM',
    description:
      'I tried to withdraw Rs.10,000 from the ATM at Banjara Hills branch. The machine showed Transaction Successful, the amount was debited from my account but cash was not dispensed. Transaction ID: ATM20260319-5521.',
    history: [
      { time: '03:45 PM', actor: 'Customer', action: 'Complaint submitted via Web Form' },
      { time: '03:46 PM', actor: 'AI System', action: 'ATM transaction ID extracted — dispute auto-classified' },
      { time: '04:00 PM', actor: 'Kavitha Nair', action: 'ATM log reviewed — confirmed cassette jam, failed dispensing' },
      { time: '04:30 PM', actor: 'Kavitha Nair', action: 'Reversal of Rs.10,000 processed successfully' },
      { time: '04:35 PM', actor: 'AI System', action: 'Resolution notification sent to customer' },
    ],
    agentResult: {
      classification: { category: 'ATM / Cash', product: 'ATM Services', severity: 'High', type: 'Failed Dispensing — Amount Debited', confidence: 99 },
      sentiment: { emotion: 'Upset', urgency: 75, score: 38, escalate: false, confidence: 93 },
      duplicate: { isDuplicate: false, similar: 1, confidence: 95 },
      compliance: { flagged: false, risk: 'LOW', reason: 'ATM dispute — standard reversal process', confidence: 97 },
      resolution: `Dear Suresh Reddy,

We have completed our investigation of transaction ATM20260319-5521.

Our ATM logs confirm cash was not dispensed due to a cassette jam. We have processed an immediate reversal of Rs.10,000 to your account — it will reflect within 2 hours.

Complaint reference: ATM-2026-0319-003

Thank you for your patience.
Union Bank of India — ATM Services`,
    },
  },
  {
    id: 'CMP-2026-004',
    customer: 'Anita Singh',
    accountNo: 'SB****5567',
    phone: '+91 65432 10987',
    channel: 'Mobile App',
    category: 'Digital Banking',
    type: 'Net Banking Locked',
    severity: 'Medium',
    sentiment: 'Anxious',
    sentimentScore: 48,
    status: 'Open',
    slaHours: 24,
    slaRemaining: '22h 10m',
    slaBreached: false,
    assignee: 'Ravi Kumar',
    branch: 'Delhi – Connaught Place',
    date: '2026-03-20',
    time: '11:00 AM',
    description:
      'My net banking account has been locked after 3 incorrect password attempts. I cannot access my account and have urgent payments to make. The self-service unlock is not working for me.',
    history: [
      { time: '11:00 AM', actor: 'Customer', action: 'Complaint submitted via Mobile App' },
      { time: '11:01 AM', actor: 'AI System', action: 'Classified: Digital Banking – Access Locked (Medium priority)' },
      { time: '11:15 AM', actor: 'Ravi Kumar', action: 'OTP-based account unlock process initiated' },
    ],
    agentResult: {
      classification: { category: 'Digital Banking', product: 'Internet Banking', severity: 'Medium', type: 'Account Locked — Failed Login Attempts', confidence: 98 },
      sentiment: { emotion: 'Anxious', urgency: 65, score: 48, escalate: false, confidence: 89 },
      duplicate: { isDuplicate: false, similar: 5, confidence: 82 },
      compliance: { flagged: false, risk: 'LOW', reason: 'Security lockout — standard security procedure', confidence: 99 },
      resolution: `Dear Anita Singh,

Your net banking account has been temporarily locked as a security precaution.

To unlock instantly:
- Call 1800-22-2244 for OTP-based unlock (under 5 minutes)
- Visit any Union Bank branch with Aadhaar/PAN

Alternatively, our team has initiated an unlock via registered mobile — check for an OTP SMS.

Complaint reference: DB-2026-0320-004`,
    },
  },
  {
    id: 'CMP-2026-005',
    customer: 'Mohammed Salim',
    accountNo: 'SB****9923',
    phone: '+91 54321 09876',
    channel: 'Social Media',
    category: 'KYC / Documents',
    type: 'KYC Rejection',
    severity: 'Medium',
    sentiment: 'Confused',
    sentimentScore: 52,
    status: 'Pending',
    slaHours: 72,
    slaRemaining: '68h 30m',
    slaBreached: false,
    assignee: 'Sunita Joshi',
    branch: 'Pune – Shivajinagar',
    date: '2026-03-19',
    time: '05:20 PM',
    description:
      'I submitted my KYC documents three times but they keep getting rejected with the message documents not acceptable. I uploaded Aadhaar, PAN and address proof. Please tell me exactly what is wrong.',
    history: [
      { time: '05:20 PM', actor: 'Customer', action: 'Complaint via Twitter/X' },
      { time: '05:21 PM', actor: 'AI System', action: 'Social media complaint captured and classified — KYC dispute' },
      { time: '05:45 PM', actor: 'Sunita Joshi', action: 'KYC records under review' },
    ],
    agentResult: {
      classification: { category: 'KYC / Documents', product: 'Account Services – KYC', severity: 'Medium', type: 'KYC Rejection — Unclear Reason', confidence: 94 },
      sentiment: { emotion: 'Confused', urgency: 55, score: 52, escalate: false, confidence: 87 },
      duplicate: { isDuplicate: true, similar: 2, confidence: 91 },
      compliance: { flagged: false, risk: 'MEDIUM', reason: 'KYC non-compliance risk if unresolved beyond 30 days', confidence: 88 },
      resolution: `Dear Mohammed Salim,

We apologize for the confusion regarding your KYC submission.

Upon review, your address proof image had insufficient resolution (below 300 DPI). Please resubmit with:
1. High-resolution scan (min 300 DPI)
2. All four document corners visible
3. File size: 50 KB to 2 MB

Resubmit at: kyc.unionbankofindia.co.in

Complaint reference: KYC-2026-0319-005`,
    },
  },
  {
    id: 'CMP-2026-006',
    customer: 'Lakshmi Iyer',
    accountNo: 'SB****3344',
    phone: '+91 43210 98765',
    channel: 'Email',
    category: 'Transactions',
    type: 'NEFT Transfer Failed',
    severity: 'High',
    sentiment: 'Angry',
    sentimentScore: 22,
    status: 'In Progress',
    slaHours: 24,
    slaRemaining: '5h 20m',
    slaBreached: false,
    assignee: 'Deepak Rao',
    branch: 'Chennai – Anna Nagar',
    date: '2026-03-20',
    time: '08:00 AM',
    description:
      'I initiated a NEFT of Rs.2,50,000 to my vendor account. The amount has been debited but the beneficiary has not received it. Reference: NEFT20260319-77821. This is a critical business payment.',
    history: [
      { time: '08:00 AM', actor: 'Customer', action: 'Email complaint — large value NEFT failure' },
      { time: '08:01 AM', actor: 'AI System', action: 'High priority — Large Amount NEFT failure, escalation triggered' },
      { time: '08:30 AM', actor: 'Deepak Rao', action: 'Coordinating with NEFT clearing team and destination bank' },
    ],
    agentResult: {
      classification: { category: 'Transactions', product: 'NEFT Transfer', severity: 'High', type: 'Failed NEFT — Amount Debited', confidence: 97 },
      sentiment: { emotion: 'Angry', urgency: 90, score: 22, escalate: true, confidence: 95 },
      duplicate: { isDuplicate: false, similar: 0, confidence: 99 },
      compliance: { flagged: false, risk: 'MEDIUM', reason: 'Large value transaction — must be traced within 24h per RBI', confidence: 92 },
      resolution: `Dear Lakshmi Iyer,

We have traced NEFT transaction NEFT20260319-77821.

The transaction is currently in pending state at the destination bank's clearing. We have sent an urgent recall request.

If not credited by March 21, 5 PM, a full refund of Rs.2,50,000 will be processed to your account.

Complaint reference: TXN-2026-0320-006`,
    },
  },
  {
    id: 'CMP-2026-007',
    customer: 'Vikram Malhotra',
    accountNo: 'SB****8876',
    phone: '+91 32109 87654',
    channel: 'Phone',
    category: 'Account Services',
    type: 'Account Frozen',
    severity: 'Critical',
    sentiment: 'Furious',
    sentimentScore: 10,
    status: 'Escalated',
    slaHours: 2,
    slaRemaining: 'BREACHED',
    slaBreached: true,
    assignee: 'Branch Manager',
    branch: 'Bengaluru – MG Road',
    date: '2026-03-19',
    time: '02:00 PM',
    description:
      'My account has been frozen without any prior notice or explanation. I cannot make any transactions. I have a family emergency and need immediate access to my money. No one at the branch is giving a clear explanation.',
    history: [
      { time: '02:00 PM', actor: 'Customer', action: 'Urgent call to contact center — family emergency' },
      { time: '02:01 PM', actor: 'AI System', action: 'CRITICAL — Account freeze complaint. Auto-escalated to Branch Manager' },
      { time: '02:05 PM', actor: 'AI System', action: 'SLA breach alert sent. Compliance flag raised' },
      { time: '02:30 PM', actor: 'Branch Manager', action: 'Under review — freeze linked to regulatory notice. Legal team engaged' },
    ],
    agentResult: {
      classification: { category: 'Account Services', product: 'Savings Account', severity: 'Critical', type: 'Account Frozen — No Prior Notice', confidence: 96 },
      sentiment: { emotion: 'Furious', urgency: 99, score: 10, escalate: true, confidence: 98 },
      duplicate: { isDuplicate: false, similar: 0, confidence: 99 },
      compliance: { flagged: true, risk: 'HIGH', reason: 'Account freeze may be court/ED ordered — legal team review mandatory', confidence: 95 },
      resolution: `Dear Vikram Malhotra,

We understand the urgency and sincerely apologize.

Your account has been temporarily frozen pursuant to a legal notice received by the bank. A senior relationship manager will contact you within 1 hour.

For immediate assistance, please visit MG Road Branch with valid government ID.

Complaint reference: ACT-2026-0319-007`,
    },
  },
  {
    id: 'CMP-2026-008',
    customer: 'Pooja Gupta',
    accountNo: 'SB****6643',
    phone: '+91 21098 76543',
    channel: 'Mobile App',
    category: 'Digital Banking',
    type: 'OTP Not Received',
    severity: 'Low',
    sentiment: 'Frustrated',
    sentimentScore: 45,
    status: 'Resolved',
    slaHours: 24,
    slaRemaining: 'Resolved',
    slaBreached: false,
    assignee: 'Auto-Resolved',
    branch: 'Jaipur – Vaishali Nagar',
    date: '2026-03-18',
    time: '07:30 PM',
    description:
      'I am not receiving OTP for net banking login. My phone is working fine and I can receive other SMS messages. This has been happening for the past 2 days and I cannot access my account.',
    history: [
      { time: '07:30 PM', actor: 'Customer', action: 'Complaint via Mobile App' },
      { time: '07:31 PM', actor: 'AI System', action: 'Duplicate detected — 8 similar OTP complaints this week. Linked to SMS gateway outage' },
      { time: '07:32 PM', actor: 'AI System', action: 'Auto-resolved — gateway issue fixed. Notification sent to customer' },
    ],
    agentResult: {
      classification: { category: 'Digital Banking', product: 'OTP / SMS Services', severity: 'Low', type: 'OTP Delivery Failure', confidence: 99 },
      sentiment: { emotion: 'Frustrated', urgency: 50, score: 45, escalate: false, confidence: 88 },
      duplicate: { isDuplicate: true, similar: 8, confidence: 97 },
      compliance: { flagged: false, risk: 'LOW', reason: 'Known technical issue — no regulatory impact', confidence: 99 },
      resolution: `Dear Pooja Gupta,

OTP delivery was affected by a temporary SMS gateway issue which has now been fully resolved.

Please try logging in again — OTPs will be delivered instantly.

If the issue persists, call 1800-22-2244.

Complaint reference: DB-2026-0318-008. Thank you for your patience.`,
    },
  },
  {
    id: 'CMP-2026-009',
    customer: 'Ramesh Bhat',
    accountNo: 'FD****1122',
    phone: '+91 10987 65432',
    channel: 'Web Form',
    category: 'Fixed Deposits',
    type: 'Interest Discrepancy',
    severity: 'Medium',
    sentiment: 'Concerned',
    sentimentScore: 50,
    status: 'Pending',
    slaHours: 72,
    slaRemaining: '55h 10m',
    slaBreached: false,
    assignee: 'Meghna Pillai',
    branch: 'Mangalore – Hampankatta',
    date: '2026-03-19',
    time: '01:00 PM',
    description:
      'My FD of Rs.5,00,000 matured on March 15, 2026. Interest credited is Rs.38,200 but my calculation at 7.65% for 1 year yields Rs.38,250. There is a discrepancy of Rs.50. Please review and rectify.',
    history: [
      { time: '01:00 PM', actor: 'Customer', action: 'Web form complaint — FD interest calculation dispute' },
      { time: '01:01 PM', actor: 'AI System', action: 'Classified: Fixed Deposit — Interest Discrepancy (Medium)' },
      { time: '01:30 PM', actor: 'Meghna Pillai', action: 'FD records pulled for verification' },
    ],
    agentResult: {
      classification: { category: 'Fixed Deposits', product: 'Term Deposit', severity: 'Medium', type: 'Interest Calculation Dispute', confidence: 93 },
      sentiment: { emotion: 'Concerned', urgency: 40, score: 50, escalate: false, confidence: 85 },
      duplicate: { isDuplicate: false, similar: 1, confidence: 89 },
      compliance: { flagged: false, risk: 'LOW', reason: 'Standard FD dispute — verify calculation methodology', confidence: 97 },
      resolution: `Dear Ramesh Bhat,

Thank you for your detailed breakdown. We have reviewed your FD account.

The difference arises from interest calculation methodology — we use a 365-day year (Actual/365). The correct interest on Rs.5,00,000 at 7.65% for 365 days is Rs.38,250.

We are crediting Rs.50 to your linked account as a correction.

Complaint reference: FD-2026-0319-009`,
    },
  },
  {
    id: 'CMP-2026-010',
    customer: 'Sunita Verma',
    accountNo: 'HL****4455',
    phone: '+91 09876 54321',
    channel: 'Email',
    category: 'Loans',
    type: 'NOC Not Issued',
    severity: 'High',
    sentiment: 'Stressed',
    sentimentScore: 30,
    status: 'In Progress',
    slaHours: 72,
    slaRemaining: '48h 00m',
    slaBreached: false,
    assignee: 'Pramod Nair',
    branch: 'Kochi – Ernakulam',
    date: '2026-03-18',
    time: '11:30 AM',
    description:
      'I fully repaid my home loan 45 days ago but have still not received my NOC and original property documents. I need these urgently to sell my property. I have been following up for 45 days without any resolution.',
    history: [
      { time: '11:30 AM', actor: 'Customer', action: 'Email complaint — 45-day follow-up on NOC' },
      { time: '11:31 AM', actor: 'AI System', action: 'High priority — Legal document delay. Compliance breach flagged (RBI: 30-day mandate)' },
      { time: '12:00 PM', actor: 'Pramod Nair', action: 'Loan closure documentation team contacted for urgent processing' },
    ],
    agentResult: {
      classification: { category: 'Loans', product: 'Home Loan', severity: 'High', type: 'NOC / Document Delay Post Closure', confidence: 96 },
      sentiment: { emotion: 'Stressed', urgency: 82, score: 30, escalate: true, confidence: 93 },
      duplicate: { isDuplicate: false, similar: 0, confidence: 99 },
      compliance: { flagged: true, risk: 'HIGH', reason: 'RBI mandates NOC within 30 days of loan closure — already breached by 15 days', confidence: 97 },
      resolution: `Dear Sunita Verma,

We sincerely apologize for the unacceptable delay. RBI guidelines require NOC issuance within 30 days — we acknowledge this breach.

We have:
1. Prioritized your NOC — ready within 48 hours
2. Arranged doorstep delivery of your original documents
3. Credited Rs.5,000 as compensation for the delay

Complaint reference: LN-2026-0318-010

Union Bank of India — Home Loan Closure Team`,
    },
  },
]
