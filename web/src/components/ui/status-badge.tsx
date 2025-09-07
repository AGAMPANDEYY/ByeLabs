import { cn } from "@/lib/utils"
import { CheckCircle, Clock, AlertCircle, XCircle, FileText, Loader2 } from "lucide-react"

export interface StatusBadgeProps {
  status: 'pending' | 'processing' | 'completed' | 'error' | 'needs_review' | 'ready' | 'failed' | 'cancelled'
  errorMessage?: string
  className?: string
}

const statusConfig = {
  pending: {
    label: 'Pending',
    className: 'bg-yellow-100 text-yellow-800',
    icon: Clock,
  },
  processing: {
    label: 'Processing',
    className: 'bg-blue-100 text-blue-800',
    icon: Loader2,
  },
  completed: {
    label: 'Completed',
    className: 'bg-green-100 text-green-800',
    icon: CheckCircle,
  },
  ready: {
    label: 'Completed',
    className: 'bg-green-100 text-green-800',
    icon: CheckCircle,
  },
  error: {
    label: 'Error',
    className: 'bg-red-100 text-red-800',
    icon: XCircle,
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-100 text-red-800',
    icon: XCircle,
  },
  cancelled: {
    label: 'Cancelled',
    className: 'bg-gray-100 text-gray-800',
    icon: XCircle,
  },
  needs_review: {
    label: 'Completed (with missing info)',
    className: 'bg-green-100 text-green-800',
    icon: AlertCircle,
  },
}

export function StatusBadge({ status, errorMessage, className }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.error // Fallback to error config
  const Icon = config.icon
  
  // Check if this is a timeout error
  const isTimeout = (status === 'error' || status === 'failed') && errorMessage?.includes('timeout')
  const displayLabel = isTimeout ? 'Timeout' : config.label

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
      {displayLabel}
    </span>
  )
}
