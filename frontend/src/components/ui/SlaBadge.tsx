import { Badge } from './Badge'

interface Props {
  breached: boolean
  /** e.g. "240h left" or time remaining */
  label: string
}

export function SlaBadge({ breached, label }: Props) {
  if (breached) {
    return (
      <Badge variant="destructive" className="uppercase tracking-wide">
        Breached
      </Badge>
    )
  }
  return (
    <Badge variant="slaSafe" className="tabular-nums font-semibold">
      {label}
    </Badge>
  )
}
