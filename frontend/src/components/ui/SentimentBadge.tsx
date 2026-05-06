import type { Sentiment } from '../../types'
import { Badge } from './Badge'
import type { BadgeProps } from './Badge'

interface Props {
  sentiment: Sentiment
}

function sentimentVariant(sentiment: Sentiment): NonNullable<BadgeProps['variant']> {
  switch (sentiment) {
    case 'Angry':
    case 'Furious':
    case 'Frustrated':
    case 'Upset':
    case 'Stressed':
      return 'sentimentWarm'
    case 'Anxious':
    case 'Confused':
      return 'sentimentPurple'
    case 'Satisfied':
      return 'sentimentPositive'
    case 'Concerned':
    case 'Neutral':
    default:
      return 'sentimentNeutral'
  }
}

/** Pill chips — warm tones vs purple family vs neutral (table grid). */
export function SentimentBadge({ sentiment }: Props) {
  return (
    <Badge variant={sentimentVariant(sentiment)}>
      {sentiment}
    </Badge>
  )
}
