export interface PipelineStep {
  id: number
  agentName: string        // must match backend agent_name exactly
  label: string            // human-friendly label shown in the UI
  description: string      // simple, non-technical description for bank staff
  color: string
  isParallel?: boolean     // part of the simultaneous fan-out group
}

// Agent names must exactly match what the backend emits in SSE events
export const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: 1,
    agentName: 'PII & Preprocessing Agent',
    label: 'Privacy & Security Check',
    description: 'Hides sensitive details like account numbers and phone numbers to protect customer privacy.',
    color: '#003087',
  },
  {
    id: 2,
    agentName: 'Duplicate Detection Agent',
    label: 'Duplicate Check',
    description: 'Checks if a similar complaint has already been registered, so we avoid handling it twice.',
    color: '#0052CC',
  },
  {
    id: 3,
    agentName: 'Classification Agent',
    label: 'Complaint Classification',
    description: 'Identifies the type of complaint — credit card, loan, ATM, digital banking, etc.',
    color: '#EA580C',
    isParallel: true,
  },
  {
    id: 4,
    agentName: 'Sentiment Agent',
    label: 'Customer Sentiment Analysis',
    description: "Detects how upset or frustrated the customer is, and whether the complaint needs escalation.",
    color: '#D97706',
    isParallel: true,
  },
  {
    id: 5,
    agentName: 'Compliance Agent',
    label: 'Compliance Check',
    description: 'Checks if this complaint falls under RBI regulatory guidelines that need special handling.',
    color: '#C8102E',
    isParallel: true,
  },
  {
    id: 6,
    agentName: 'Severity Agent',
    label: 'Severity Assessment',
    description: 'Rates how serious this complaint is on a scale of 1 to 5 based on financial impact.',
    color: '#7C3AED',
    isParallel: true,
  },
  {
    id: 7,
    agentName: 'Memory & RAG Agent',
    label: 'Knowledge Retrieval',
    description: 'Searches our knowledge base for similar past cases and best resolutions.',
    color: '#0284C7',
  },
  {
    id: 8,
    agentName: 'Resolution Generator',
    label: 'Draft Response Generation',
    description: 'AI writes a personalised resolution letter for the customer based on all the analysis above.',
    color: '#16A34A',
  },
  {
    id: 9,
    agentName: 'Grounding & Fact Check Agent',
    label: 'Accuracy Verification',
    description: 'Verifies that the AI response is factually accurate and follows bank policies.',
    color: '#0369A1',
  },
  {
    id: 10,
    agentName: 'Risk-Aware Routing',
    label: 'Routing Decision',
    description: 'Decides whether to send the response automatically or route it to a human agent for review.',
    color: '#4F46E5',
  },
]

export function getStepByAgentName(name: string): PipelineStep | undefined {
  return PIPELINE_STEPS.find((s) => s.agentName === name)
}
