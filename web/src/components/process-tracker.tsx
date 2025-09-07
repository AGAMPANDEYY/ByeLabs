'use client'

import { CheckCircle2, Clock, AlertCircle, Loader2 } from 'lucide-react'

export interface ProcessStep {
  id: string
  name: string
  description: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  error?: string
}

interface ProcessTrackerProps {
  steps: ProcessStep[]
  currentStep?: string
  className?: string
}

export function ProcessTracker({ steps, currentStep, className = '' }: ProcessTrackerProps) {
  const getStepIcon = (step: ProcessStep) => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-600" />
      default:
        return <Clock className="w-5 h-5 text-gray-400" />
    }
  }

  const getStepColor = (step: ProcessStep) => {
    switch (step.status) {
      case 'completed':
        return 'border-green-500 bg-green-50'
      case 'processing':
        return 'border-blue-500 bg-blue-50'
      case 'error':
        return 'border-red-500 bg-red-50'
      default:
        return 'border-gray-300 bg-white'
    }
  }

  const getTextColor = (step: ProcessStep) => {
    switch (step.status) {
      case 'completed':
        return 'text-green-700'
      case 'processing':
        return 'text-blue-700'
      case 'error':
        return 'text-red-700'
      default:
        return 'text-gray-500'
    }
  }

  return (
    <div className={`w-full ${className}`}>
      <div className="relative">
        {/* Progress Line */}
        <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-gray-200">
          <div 
            className="w-full bg-blue-500 transition-all duration-500 ease-in-out"
            style={{ 
              height: `${(steps.filter(s => s.status === 'completed').length / Math.max(steps.length - 1, 1)) * 100}%` 
            }}
          />
        </div>

        {/* Steps */}
        <div className="space-y-6">
          {steps.map((step, index) => (
            <div key={step.id} className="relative flex items-start space-x-4">
              {/* Step Circle */}
              <div className={`
                relative z-10 flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all duration-300
                ${getStepColor(step)}
              `}>
                {getStepIcon(step)}
              </div>

              {/* Step Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <h3 className={`text-sm font-medium ${getTextColor(step)}`}>
                    {step.name}
                  </h3>
                  {step.status === 'processing' && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Processing...
                    </span>
                  )}
                  {step.status === 'error' && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      Error
                    </span>
                  )}
                </div>
                <p className={`text-sm mt-1 ${getTextColor(step)}`}>
                  {step.description}
                </p>
                {step.error && (
                  <p className="text-xs text-red-600 mt-1 bg-red-50 p-2 rounded">
                    {step.error}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Circular Process Tracker (Alternative Design)
export function CircularProcessTracker({ steps, currentStep, className = '' }: ProcessTrackerProps) {
  const completedSteps = steps.filter(s => s.status === 'completed').length
  const totalSteps = steps.length
  const progress = (completedSteps / totalSteps) * 100

  return (
    <div className={`flex flex-col items-center space-y-6 ${className}`}>
      {/* Circular Progress */}
      <div className="relative w-32 h-32">
        <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 120 120">
          {/* Background Circle */}
          <circle
            cx="60"
            cy="60"
            r="50"
            stroke="currentColor"
            strokeWidth="8"
            fill="none"
            className="text-gray-200"
          />
          {/* Progress Circle */}
          <circle
            cx="60"
            cy="60"
            r="50"
            stroke="currentColor"
            strokeWidth="8"
            fill="none"
            strokeDasharray={`${2 * Math.PI * 50}`}
            strokeDashoffset={`${2 * Math.PI * 50 * (1 - progress / 100)}`}
            className="text-blue-500 transition-all duration-500 ease-in-out"
            strokeLinecap="round"
          />
        </svg>
        
        {/* Center Content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-2xl font-bold text-gray-900">
            {completedSteps}/{totalSteps}
          </div>
          <div className="text-xs text-gray-500 text-center">
            Steps Complete
          </div>
        </div>
      </div>

      {/* Current Step Display */}
      <div className="text-center">
        <div className="text-lg font-semibold text-gray-900">
          {steps.find(s => s.status === 'processing')?.name || 
           steps.find(s => s.status === 'error')?.name || 
           'Processing Complete'}
        </div>
        <div className="text-sm text-gray-600 mt-1">
          {steps.find(s => s.status === 'processing')?.description || 
           steps.find(s => s.status === 'error')?.description || 
           'All steps completed successfully'}
        </div>
      </div>

      {/* Step List */}
      <div className="w-full max-w-md space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center space-x-3">
            <div className={`
              w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium
              ${step.status === 'completed' ? 'bg-green-500 text-white' :
                step.status === 'processing' ? 'bg-blue-500 text-white' :
                step.status === 'error' ? 'bg-red-500 text-white' :
                'bg-gray-300 text-gray-600'}
            `}>
              {step.status === 'completed' ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : step.status === 'processing' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : step.status === 'error' ? (
                <AlertCircle className="w-4 h-4" />
              ) : (
                index + 1
              )}
            </div>
            <span className={`text-sm ${
              step.status === 'completed' ? 'text-green-700' :
              step.status === 'processing' ? 'text-blue-700' :
              step.status === 'error' ? 'text-red-700' :
              'text-gray-500'
            }`}>
              {step.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
