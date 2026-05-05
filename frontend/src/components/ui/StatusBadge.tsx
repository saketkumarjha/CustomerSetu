import type { Status } from '../../types'
import { getStatusClasses } from '../../utils/styles'

interface Props {
  status: Status
}

export function StatusBadge({ status }: Props) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${getStatusClasses(status)}`}>
      {status}
    </span>
  )
}
