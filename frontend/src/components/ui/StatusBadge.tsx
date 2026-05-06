import type { Status } from '../../types'
import { Badge } from './Badge'
import type { BadgeProps } from './Badge'

interface Props {
  status: Status
  className?: string
}

function statusVariant(status: Status): NonNullable<BadgeProps['variant']> {
  switch (status) {
    case 'Open':
      return 'statusOpen'
    case 'In Progress':
      return 'statusInProgress'
    case 'Pending':
      return 'statusPending'
    case 'Resolved':
      return 'statusResolved'
    case 'Escalated':
      return 'statusEscalated'
  }
}

export function StatusBadge({ status, className }: Props) {
  return (
    <Badge variant={statusVariant(status)} className={className}>
      {status}
    </Badge>
  )
}
