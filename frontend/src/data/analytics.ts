import type { TrendDataPoint, CategoryDataPoint, SentimentDataPoint, SlaDataPoint } from '../types'

export const TREND_DATA: TrendDataPoint[] = [
  { month: "Oct '25", total: 342, resolved: 298, critical: 28 },
  { month: "Nov '25", total: 318, resolved: 290, critical: 22 },
  { month: "Dec '25", total: 425, resolved: 365, critical: 45 },
  { month: "Jan '26", total: 389, resolved: 341, critical: 35 },
  { month: "Feb '26", total: 356, resolved: 320, critical: 30 },
  { month: "Mar '26", total: 287, resolved: 245, critical: 18 },
]

export const CATEGORY_DATA: CategoryDataPoint[] = [
  { name: 'Transactions', count: 89 },
  { name: 'Digital Banking', count: 72 },
  { name: 'Credit Card', count: 58 },
  { name: 'Loans', count: 45 },
  { name: 'ATM / Cash', count: 38 },
  { name: 'KYC / Docs', count: 25 },
]

export const SENTIMENT_DATA: SentimentDataPoint[] = [
  { name: 'Angry', value: 35 },
  { name: 'Frustrated', value: 28 },
  { name: 'Neutral', value: 20 },
  { name: 'Confused', value: 10 },
  { name: 'Satisfied', value: 7 },
]

export const SLA_DATA: SlaDataPoint[] = [
  { month: 'Oct', met: 82, breached: 18 },
  { month: 'Nov', met: 85, breached: 15 },
  { month: 'Dec', met: 74, breached: 26 },
  { month: 'Jan', met: 79, breached: 21 },
  { month: 'Feb', met: 83, breached: 17 },
  { month: 'Mar', met: 88, breached: 12 },
]

export const SENTIMENT_COLORS = ['#003087', '#244f9e', '#456fad', '#6b8fbf', '#94adc9']

export const AI_METRICS = [
  { label: 'Classification accuracy', value: '98.2%', color: '#003087' },
  { label: 'Draft responses produced', value: '95.7%', color: '#003087' },
  { label: 'Duplicates detected today', value: '3', color: '#64748B' },
  { label: 'Compliance reviews open', value: '4', color: '#64748B' },
  { label: 'Average model confidence', value: '94.1%', color: '#003087' },
]
