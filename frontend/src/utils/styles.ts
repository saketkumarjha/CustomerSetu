import type { Sentiment, Channel } from '../types'

/** Union Bank primary hue + neutral steps — use for charts instead of rainbow palettes */
export const CHART_PALETTE = ['#003087', '#244f9e', '#456fad', '#6b8fbf', '#94adc9', '#bcccdc'] as const

/** Table / inline sentiment — single muted tone (finance UI) */
export function getSentimentColor(_sentiment: Sentiment): string {
  return '#475569'
}

export function getChannelIcon(channel: Channel): string {
  switch (channel) {
    case 'Email':
      return 'Mail'
    case 'Phone':
      return 'Phone'
    case 'Web Form':
      return 'Globe'
    case 'Mobile App':
      return 'Smartphone'
    case 'Social Media':
      return 'MessageSquare'
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
  if (actor === 'AI System') return '#64748B'
  if (actor === 'Customer') return '#003087'
  return '#C8102E'
}
