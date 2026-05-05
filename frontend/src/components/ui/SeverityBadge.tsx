import type { Severity } from '../../types'
import { getSeverityClasses } from '../../utils/styles'

interface Props {
  severity: Severity
}

export function SeverityBadge({ severity }: Props) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${getSeverityClasses(severity)}`}>
      {severity}
    </span>
  )
}
