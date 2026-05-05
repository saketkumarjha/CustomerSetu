import type { Severity, Status, Sentiment, Channel } from '../types'

export function getSeverityClasses(severity: Severity): string {
  switch (severity) {
    case 'Critical': return 'bg-red-100 text-red-800'
    case 'High': return 'bg-amber-100 text-amber-800'
    case 'Medium': return 'bg-blue-100 text-blue-800'
    case 'Low': return 'bg-green-100 text-green-700'
  }
}

export function getStatusClasses(status: Status): string {
  switch (status) {
    case 'Open': return 'bg-blue-50 text-blue-700'
    case 'In Progress': return 'bg-amber-50 text-amber-700'
    case 'Pending': return 'bg-slate-100 text-slate-600'
    case 'Resolved': return 'bg-green-50 text-green-700'
    case 'Escalated': return 'bg-red-50 text-red-700'
  }
}

export function getSentimentColor(sentiment: Sentiment): string {
  switch (sentiment) {
    case 'Angry':
    case 'Furious': return '#DC2626'
    case 'Frustrated':
    case 'Stressed': return '#EA580C'
    case 'Upset': return '#D97706'
    case 'Anxious':
    case 'Confused': return '#7C3AED'
    case 'Concerned': return '#0284C7'
    case 'Neutral': return '#6B7280'
    case 'Satisfied': return '#16A34A'
  }
}

export function getChannelIcon(channel: Channel): string {
  switch (channel) {
    case 'Email': return 'Mail'
    case 'Phone': return 'Phone'
    case 'Web Form': return 'Globe'
    case 'Mobile App': return 'Smartphone'
    case 'Social Media': return 'MessageSquare'
  }
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

export function getActorColor(actor: string): string {
  if (actor === 'AI System') return '#7C3AED'
  if (actor === 'Customer') return '#003087'
  return '#C8102E'
}
