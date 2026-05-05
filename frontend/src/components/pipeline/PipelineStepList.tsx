import { CheckCircle2, Loader2 } from 'lucide-react'
import { PIPELINE_STEPS } from './pipelineSteps'

interface Props {
  currentStep: number
  running: boolean
}

export function PipelineStepList({ currentStep, running }: Props) {
  return (
    <div className="relative">
      {/* Vertical track */}
      <div className="absolute left-5 top-4 bottom-4 w-px bg-gray-200" />

      {PIPELINE_STEPS.map((step) => {
        const done = currentStep > step.id
        const active = currentStep === step.id && running

        return (
          <div key={step.id} className="flex items-start gap-4 mb-5 last:mb-0">
            {/* Node */}
            <div
              className="relative z-10 w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 border-2"
              style={{
                backgroundColor: done || active ? `${step.color}18` : '#F9FAFB',
                borderColor: done || active ? step.color : '#E5E7EB',
                boxShadow: active ? `0 0 16px ${step.color}44` : 'none',
                transform: active ? 'scale(1.1)' : 'scale(1)',
              }}
            >
              {done ? (
                <CheckCircle2 size={16} style={{ color: step.color }} />
              ) : active ? (
                <Loader2 size={16} className="animate-spin" style={{ color: step.color }} />
              ) : (
                <div className="w-2 h-2 rounded-full bg-gray-300" />
              )}
            </div>

            {/* Text */}
            <div className="flex-1 pt-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`text-sm font-semibold transition-colors ${
                    done || active ? 'text-gray-800' : 'text-gray-400'
                  }`}
                >
                  {step.label}
                </span>
                {active && (
                  <span
                    className="text-xs text-white px-2 py-0.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: step.color }}
                  >
                    Processing…
                  </span>
                )}
                {done && (
                  <span className="text-xs text-green-600 font-semibold flex-shrink-0">Complete</span>
                )}
              </div>
              <p className={`text-xs mt-0.5 leading-relaxed ${done || active ? 'text-gray-500' : 'text-gray-300'}`}>
                {step.description}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
