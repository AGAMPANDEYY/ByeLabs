import { cn } from "@/lib/utils"
import { CheckCircle, Clock, AlertCircle, XCircle, FileText, Loader2 } from "lucide-react"

export interface StatusBadgeProps {
  status: 'pending' | 'processing' | 'needs_review' | 'ready' | 'exported' | 'failed' | 'cancelled'
  className?: string
}

const statusConfig = {
  pending: {
    label: 'Pending',
    className: 'bg-gray-100 text-gray-700',
    icon: Clock,
  },
  processing: {
    label: 'Processing',
    className: 'bg-primary-100 text-primary-700',
    icon: Loader2,
  },
  needs_review: {
    label: 'Needs Review',
    className: 'bg-amber-100 text-amber-700',
    icon: AlertCircle,
  },
  ready: {
    label: 'Ready',
    className: 'bg-green-100 text-green-700',
    icon: CheckCircle,
  },
  exported: {
    label: 'Exported',
    className: 'bg-indigo-100 text-indigo-700',
    icon: FileText,
  },
  failed: {
    label: 'Failed',
    className: 'bg-rose-100 text-rose-700',
    icon: XCircle,
  },
  cancelled: {
    label: 'Cancelled',
    className: 'bg-gray-100 text-gray-500',
    icon: XCircle,
  },
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium',
        config.className,
        status === 'processing' && 'animate-pulse',
        className
      )}
    >
      <Icon 
        className={cn(
          'w-3 h-3',
          status === 'processing' && 'animate-spin'
        )} 
      />
      {config.label}
    </span>
  )
}
