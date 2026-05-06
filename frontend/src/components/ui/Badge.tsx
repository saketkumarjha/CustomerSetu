import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

/**
 * Pill badges — pale fill + darker label (finance / ops tables).
 */
export const badgeVariants = cva(
  'inline-flex items-center justify-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold leading-none tracking-wide whitespace-nowrap transition-colors',
  {
    variants: {
      variant: {
        default:
          'border-slate-200/90 bg-white text-slate-800 shadow-[0_1px_0_rgba(0,0,0,0.03)]',
        secondary:
          'border-slate-200/80 bg-slate-100 text-slate-800',
        outline:
          'border-slate-200/90 bg-slate-50 text-slate-700',
        accent:
          'border-sky-200/80 bg-sky-50 text-sky-900',
        muted:
          'border-slate-200/70 bg-slate-100/90 text-slate-700',
        destructive:
          'border-red-200/90 bg-red-50 text-red-900',

        severityCritical:
          'border-red-200/90 bg-red-50 text-red-900',
        severityHigh:
          'border-amber-200/80 bg-amber-50 text-amber-900',
        severityMedium:
          'border-sky-200/80 bg-sky-50 text-sky-900',
        severityLow:
          'border-slate-200/80 bg-slate-100 text-slate-800',

        statusOpen:
          'border-blue-200/80 bg-blue-50 text-blue-900',
        statusInProgress:
          'border-indigo-200/80 bg-indigo-50 text-indigo-900',
        statusPending:
          'border-amber-200/80 bg-amber-50 text-amber-900',
        statusResolved:
          'border-emerald-200/80 bg-emerald-50 text-emerald-900',
        statusEscalated:
          'border-red-200/90 bg-red-50 text-red-900',

        sentimentWarm:
          'border-amber-200/70 bg-amber-50 text-amber-900',
        sentimentPurple:
          'border-violet-200/70 bg-violet-50 text-violet-900',
        sentimentNeutral:
          'border-slate-200/80 bg-slate-100 text-slate-800',
        sentimentPositive:
          'border-emerald-200/70 bg-emerald-50 text-emerald-900',

        channel:
          'border-slate-200/80 bg-slate-50 text-slate-700',

        slaSafe:
          'border-emerald-200/60 bg-emerald-50/90 text-emerald-900',
      },
    },
    defaultVariants: {
      variant: 'outline',
    },
  },
)

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
