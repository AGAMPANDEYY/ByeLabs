'use client'

import { useParams } from 'next/navigation'
import { useJob } from '@/hooks/useJobs'
import { apiClient } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { ProcessTracker, CircularProcessTracker } from '@/components/process-tracker'
import { ExportStatus } from '@/components/excel-preview'
import { 
  ArrowLeft, 
  Download, 
  RefreshCw, 
  FileText, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Eye,
  Play
} from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

export default function JobDetailPage() {
  const params = useParams()
  const jobId = parseInt(params.id as string)
  const { job, loading, refetch } = useJob(jobId)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // Define processing steps based on job status
  const getProcessingSteps = () => {
    const steps: Array<{
      id: string
      name: string
      description: string
      status: 'pending' | 'processing' | 'completed' | 'error'
      error?: string
    }> = [
      {
        id: 'intake',
        name: 'Email Intake',
        description: 'Parse and validate email content',
        status: 'completed'
      },
      {
        id: 'classification',
        name: 'Classification',
        description: 'Classify email type and content',
        status: 'completed'
      },
      {
        id: 'extraction',
        name: 'Data Extraction',
        description: 'Extract provider information from content',
        status: job?.status === 'processing' ? 'processing' : 'completed'
      },
      {
        id: 'normalization',
        name: 'Data Normalization',
        description: 'Normalize and standardize data formats',
        status: job?.status === 'processing' ? 'processing' : 'completed'
      },
      {
        id: 'validation',
        name: 'Data Validation',
        description: 'Validate data quality and completeness',
        status: job?.status === 'processing' ? 'processing' : 'completed'
      },
      {
        id: 'versioning',
        name: 'Version Control',
        description: 'Create version and audit trail',
        status: job?.status === 'processing' ? 'processing' : 'completed'
      },
      {
        id: 'export',
        name: 'Excel Export',
        description: 'Generate Excel file with standardized format',
        status: job?.status === 'completed' ? 'completed' : 
                job?.status === 'needs_review' ? 'completed' :
                job?.status === 'error' ? 'error' : 'pending'
      }
    ]

    // Update step statuses based on job status
    if (job?.status === 'error') {
      steps.forEach(step => {
        if (step.status === 'processing') {
          step.status = 'error'
          step.error = job.error_message || 'Processing failed'
        }
      })
    }

    return steps
  }

  const handleExport = async () => {
    if (!job) return

    setExporting(true)
    setExportError(null)

    try {
      // Check if there are existing exports in the job details
      if (job.artifacts?.exports && job.artifacts.exports.length > 0) {
        // Use the first available export
        const exportData = job.artifacts.exports[0]
        const blob = await apiClient.downloadExport(exportData.id)
        
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `roster_export_${job.id}.xlsx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } else {
        // No existing export, create a new one
        const exportData = await apiClient.createExport(job.id)
        const blob = await apiClient.downloadExport(exportData.id)
        
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `roster_export_${job.id}.xlsx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div className="container-custom py-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container-custom py-8">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Job Not Found</h1>
          <p className="text-gray-600 mb-4">The requested job could not be found.</p>
          <Link href="/inbox">
            <Button variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Inbox
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="container-custom py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <Link href="/inbox">
            <Button variant="outline" size="icon">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Job #{job.id}</h1>
            <p className="text-gray-600">
              {job.email?.subject || job.email_subject || 'Provider Roster Processing'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <Button
            variant="outline"
            onClick={refetch}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          
          {['completed', 'needs_review'].includes(job.status) && (
            <Button
              onClick={handleExport}
              disabled={exporting}
              className="btn-primary"
            >
              {exporting ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  Export Excel
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Job Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Status Card */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Processing Status</h2>
              <StatusBadge status={job.status} errorMessage={job.error_message} />
            </div>
            
            <div className="space-y-4">
              <div className="flex items-center space-x-3">
                <Clock className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-600">Created</p>
                  <p className="font-medium">{new Date(job.created_at).toLocaleString()}</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <Clock className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm text-gray-600">Last Updated</p>
                  <p className="font-medium">{new Date(job.updated_at).toLocaleString()}</p>
                </div>
              </div>
              
              {(job.email?.from_addr || job.email_from) && (
                <div className="flex items-center space-x-3">
                  <FileText className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-600">From</p>
                    <p className="font-medium">{job.email?.from_addr || job.email_from}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Process Tracker */}
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Processing Pipeline</h2>
            <ProcessTracker steps={getProcessingSteps()} />
          </div>

          {/* Excel Export Section */}
          {['completed', 'needs_review'].includes(job.status) && (
            <ExportStatus jobId={job.id} />
          )}

          {/* Error Message */}
          {job.error_message && (
            <div className="card p-6 border-red-200 bg-red-50">
              <div className="flex items-center space-x-3">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <div>
                  <h3 className="font-semibold text-red-900">Processing Error</h3>
                  <p className="text-red-700 mt-1">{job.error_message}</p>
                </div>
              </div>
            </div>
          )}

          {/* Export Error */}
          {exportError && (
            <div className="card p-6 border-red-200 bg-red-50">
              <div className="flex items-center space-x-3">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <div>
                  <h3 className="font-semibold text-red-900">Export Error</h3>
                  <p className="text-red-700 mt-1">{exportError}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Circular Progress */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Progress Overview</h3>
            <CircularProcessTracker steps={getProcessingSteps()} />
          </div>

          {/* Job Stats */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Job Statistics</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Records</span>
                <span className="font-medium">{job.total_records || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Processed Records</span>
                <span className="font-medium">{job.processed_records || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Success Rate</span>
                <span className="font-medium">
                  {job.total_records ? 
                    `${Math.round((job.processed_records || 0) / job.total_records * 100)}%` : 
                    '0%'
                  }
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Actions</h3>
            <div className="space-y-3">
              {job.status === 'error' && (
                <Button
                  onClick={() => {
                    // Implement retry logic
                    console.log('Retry job:', job.id)
                  }}
                  className="w-full"
                  variant="outline"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Retry Processing
                </Button>
              )}
              
              <Link href="/inbox" className="block">
                <Button variant="outline" className="w-full">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Inbox
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
