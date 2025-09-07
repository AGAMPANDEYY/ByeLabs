'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { getJobs, processJob, type Job } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { 
  Eye, 
  Play, 
  RefreshCw, 
  AlertCircle,
  FileText,
  Upload
} from 'lucide-react'
import Link from 'next/link'

export default function InboxPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<Set<number>>(new Set())

  const fetchJobs = async () => {
    try {
      const data = await getJobs()
      setJobs(data)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs()
    
    // Poll for updates every 4 seconds
    const interval = setInterval(fetchJobs, 4000)
    return () => clearInterval(interval)
  }, [])

  const handleProcessJob = async (jobId: number) => {
    setProcessing(prev => new Set(prev).add(jobId))
    try {
      await processJob(jobId)
      // Refresh jobs after processing starts
      setTimeout(fetchJobs, 1000)
    } catch (error) {
      console.error('Failed to process job:', error)
    } finally {
      setProcessing(prev => {
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
          <h1 className="text-3xl font-bold text-gray-900">Inbox</h1>
          <p className="text-gray-600 mt-2">
            Manage and process your provider roster emails
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <Button
            variant="outline"
            onClick={fetchJobs}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          
          <Button
            variant="gradient"
            onClick={() => document.getElementById('file-upload')?.click()}
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload .eml
          </Button>
          
          <input
            id="file-upload"
            type="file"
            accept=".eml"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0]
              if (!file) return
              
              try {
                const formData = new FormData()
                formData.append('eml', file)
                
                const response = await fetch('http://localhost:8000/ingest', {
                  method: 'POST',
                  body: formData,
                })
                
                if (response.ok) {
                  const result = await response.json()
                  window.location.href = `/jobs/${result.job_id}`
                } else {
                  alert('Upload failed. Please try again.')
                }
              } catch (error) {
                console.error('Upload error:', error)
                alert('Upload failed. Please try again.')
              }
            }}
          />
        </div>
      </div>

      {jobs.length === 0 ? (
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
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">
                        {job.subject || 'No subject'}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600">
                        {job.from_addr || 'Unknown'}
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
                          <Button variant="ghost" size="sm">
                            <Eye className="w-4 h-4" />
                          </Button>
                        </Link>
                        
                        {(job.status === 'pending' || job.status === 'failed') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleProcessJob(job.id)}
                            disabled={processing.has(job.id)}
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
    </div>
  )
}
