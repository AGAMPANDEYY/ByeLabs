'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { useJobs } from '@/hooks/useJobs'
import { FileUpload } from '@/components/file-upload'
import { formatDate } from '@/lib/utils'
import { apiClient } from '@/lib/api'
import * as XLSX from 'xlsx'
import { 
  Eye, 
  Play, 
  RefreshCw, 
  AlertCircle,
  FileText,
  Upload,
  Download,
  Table,
  CheckCircle
} from 'lucide-react'
import Link from 'next/link'

export default function InboxPage() {
  const { jobs, loading, uploadEmail, resumeJob, refetch } = useJobs()
  const [processing, setProcessing] = useState<Set<number>>(new Set())
  const [downloading, setDownloading] = useState<Set<number>>(new Set())
  const [previewJobId, setPreviewJobId] = useState<number | null>(null)
  const [previewData, setPreviewData] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const handleProcessJob = async (jobId: number) => {
    setProcessing(prev => new Set(prev).add(jobId))
    try {
      await resumeJob(jobId)
    } catch (error) {
      console.error('Failed to process job:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to process job'
      if (errorMessage.includes('timeout')) {
        alert('Job processing timed out. The job has been marked as failed.')
      } else {
        alert('Failed to process job. Please try again.')
      }
    } finally {
      setProcessing(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  const handleUploadSuccess = (jobId: number) => {
    console.log('Upload successful, job ID:', jobId)
    // Jobs will automatically refresh via the hook
  }

  const handlePreviewTable = async (jobId: number) => {
    setPreviewJobId(jobId)
    setPreviewLoading(true)
    setPreviewData(null)
    
    try {
      // Get job details to find existing exports
      const jobDetails = await apiClient.getJob(jobId)
      
      if (jobDetails.artifacts?.exports && jobDetails.artifacts.exports.length > 0) {
        // Use the first available export
        const exportData = jobDetails.artifacts.exports[0]
        const blob = await apiClient.downloadExport(exportData.id)
        
        // Parse the actual Excel data from the backend pipeline
        const arrayBuffer = await blob.arrayBuffer()
        const workbook = XLSX.read(arrayBuffer, { type: 'array' })
        const sheetName = workbook.SheetNames[0] // Get first sheet
        const worksheet = workbook.Sheets[sheetName]
        
        // Convert to JSON
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
        
        if (jsonData.length > 0) {
          const headers = jsonData[0] as string[]
          const rows = jsonData.slice(1).map((row: unknown) => {
            const rowArray = row as any[]
            const rowData: any = {}
            headers.forEach((header, index) => {
              rowData[header] = rowArray[index] || null
            })
            return rowData
          }).filter(row => Object.values(row).some(value => value !== null && value !== ''))
          
          const realData = {
            headers,
            rows
          }
          
          setPreviewData(realData)
        } else {
          setPreviewData(null)
        }
      } else {
        setPreviewData(null)
      }
    } catch (error) {
      console.error('Preview failed:', error)
      setPreviewData(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const closePreview = () => {
    setPreviewJobId(null)
    setPreviewData(null)
  }

  const handleDownloadExcel = async (jobId: number) => {
    setDownloading(prev => new Set(prev).add(jobId))
    try {
      // First get the job details to find existing exports
      const jobDetails = await apiClient.getJob(jobId)
      
      // Check if there are existing exports in the job details
      if (jobDetails.artifacts?.exports && jobDetails.artifacts.exports.length > 0) {
        // Use the first available export
        const exportData = jobDetails.artifacts.exports[0]
        const blob = await apiClient.downloadExport(exportData.id)
        
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `roster_export_${jobId}.xlsx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } else {
        // No existing export, create a new one
        const exportData = await apiClient.createExport(jobId)
        const blob = await apiClient.downloadExport(exportData.id)
        
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `roster_export_${jobId}.xlsx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (error) {
      console.error('Download failed:', error)
      alert('Download failed. Please try again.')
    } finally {
      setDownloading(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  if (loading) {
    return (
      <div className="container-custom py-8">
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card p-6">
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2"></div>
              <div className="h-3 bg-gray-200 rounded w-1/3"></div>
            </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="container-custom py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Roster Table</h1>
          <p className="text-gray-600 mt-2">
            View and manage all processed provider roster emails with their status and extracted data
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="w-64">
            <FileUpload 
              onUploadSuccess={handleUploadSuccess}
              onUploadError={(error) => console.error('Upload error:', error)}
            />
          </div>
          
          {Array.isArray(jobs) && jobs.some(job => ['completed', 'needs_review'].includes(job.status)) && (
            <Button
              variant="outline"
              onClick={() => {
                const completedJobs = jobs.filter(job => ['completed', 'needs_review'].includes(job.status))
                completedJobs.forEach(job => handleDownloadExcel(job.id))
              }}
              disabled={downloading.size > 0}
            >
              <Download className="w-4 h-4 mr-2" />
              Download All Completed
            </Button>
          )}
          
          <Button
            variant="outline"
            onClick={refetch}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {!Array.isArray(jobs) || jobs.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            No jobs yet
          </h3>
          <p className="text-gray-600 mb-6">
            Upload your first .eml file to get started with roster processing
          </p>
          <Button
            variant="gradient"
            onClick={() => document.getElementById('file-upload')?.click()}
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload .eml
          </Button>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Status
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Subject
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  From
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Received
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Issues
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
                {Array.isArray(jobs) && jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <StatusBadge status={job.status} errorMessage={job.error_message} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">
                        {job.email?.subject || job.subject || 'No subject'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600">
                        {job.email?.from_addr || job.from_addr || 'Unknown'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600">
                        {formatDate(job.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {job.issues_count ? (
                        <div className="flex items-center text-sm text-amber-600">
                          <AlertCircle className="w-4 h-4 mr-1" />
                          {job.issues_count}
                        </div>
                      ) : (
                        <span className="text-sm text-gray-400">None</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <Link href={`/jobs/${job.id}`}>
                          <Button variant="ghost" size="sm" title="View Details">
                            <Eye className="w-4 h-4" />
                          </Button>
                        </Link>
                        
                        {['completed', 'needs_review'].includes(job.status) && (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            title="Preview Data Table"
                            onClick={() => handlePreviewTable(job.id)}
                          >
                            <Table className="w-4 h-4 text-green-600" />
                          </Button>
                        )}
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadExcel(job.id)}
                          disabled={!['completed', 'needs_review'].includes(job.status) || downloading.has(job.id)}
                          title={['completed', 'needs_review'].includes(job.status) ? "Download Excel" : "Processing - Download will be available when complete"}
                          className={['completed', 'needs_review'].includes(job.status) ? 'text-blue-600 hover:text-blue-700' : 'text-gray-400'}
                        >
                          {downloading.has(job.id) ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Download className="w-4 h-4" />
                          )}
                        </Button>
                        
                        {(job.status === 'pending' || job.status === 'error') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleProcessJob(job.id)}
                            disabled={processing.has(job.id)}
                            title="Retry Processing"
                          >
                            {processing.has(job.id) ? (
                              <RefreshCw className="w-4 h-4 animate-spin" />
                            ) : (
                              <Play className="w-4 h-4" />
                            )}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewJobId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <Table className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Excel Export</h2>
                  <p className="text-sm text-gray-600">Job #{previewJobId}</p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <Button
                  variant="outline"
                  onClick={closePreview}
                  className="flex items-center space-x-2"
                >
                  <Eye className="w-4 h-4" />
                  <span>Hide Preview</span>
                </Button>
                <Button
                  onClick={() => handleDownloadExcel(previewJobId)}
                  className="btn-primary"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)]">
              {previewLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-3 text-gray-600">Loading preview...</span>
                </div>
              ) : previewData ? (
                <div>
                  {/* Preview Header */}
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-gray-900">
                      Preview ({previewData.rows.length} rows)
                    </h3>
                    <div className="flex items-center space-x-2 text-green-600">
                      <CheckCircle className="w-4 h-4" />
                      <span className="text-sm font-medium">Ready for Download</span>
                    </div>
                  </div>

                  {/* Data Table */}
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-gray-50">
                          <tr>
                            {previewData.headers.map((header: string, index: number) => (
                              <th
                                key={index}
                                className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r border-gray-200 last:border-r-0"
                              >
                                {header}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {previewData.rows.map((row: any, rowIndex: number) => (
                            <tr key={rowIndex} className="hover:bg-gray-50">
                              {previewData.headers.map((header: string, colIndex: number) => (
                                <td
                                  key={colIndex}
                                  className="px-4 py-3 text-sm text-gray-900 border-r border-gray-200 last:border-r-0"
                                >
                                  {row[header] || '-'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Preview Available</h3>
                  <p className="text-gray-600">This job doesn't have any exported data to preview.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
