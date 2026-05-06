import type { Channel } from '../../types'
import { Badge } from './Badge'
import { cn } from '../../lib/utils'

interface Props {
  channel: Channel
  className?: string
}

/** Channel label — soft slate pill (text only). */
export function ChannelBadge({ channel, className }: Props) {
  return (
    <Badge variant="channel" className={cn(className)}>
      {channel}
    </Badge>
  )
}
