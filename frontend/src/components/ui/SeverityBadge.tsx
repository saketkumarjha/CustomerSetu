import type { Severity } from '../../types'
import { Badge } from './Badge'
import type { BadgeProps } from './Badge'

interface Props {
  severity: Severity
  className?: string
}

function severityVariant(severity: Severity): NonNullable<BadgeProps['variant']> {
  switch (severity) {
    case 'Critical':
      return 'severityCritical'
    case 'High':
      return 'severityHigh'
    case 'Medium':
      return 'severityMedium'
    case 'Low':
      return 'severityLow'
  }
}

export function SeverityBadge({ severity, className }: Props) {
  return (
    <Badge variant={severityVariant(severity)} className={className}>
      {severity}
    </Badge>
  )
}
