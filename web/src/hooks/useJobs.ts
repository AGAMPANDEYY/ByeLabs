'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiClient, Job } from '@/lib/api'

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getJobs()
      setJobs(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs')
      setJobs([]) // Set empty array on error
    } finally {
      setLoading(false)
    }
  }, [])

  const uploadEmail = useCallback(async (file: File) => {
    try {
      setError(null)
      const newJob = await apiClient.uploadEmail(file)
      setJobs(prev => Array.isArray(prev) ? [newJob, ...prev] : [newJob])
      return newJob
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed'
      setError(errorMessage)
      throw new Error(errorMessage)
    }
  }, [])

  const resumeJob = useCallback(async (jobId: number) => {
    try {
      setError(null)
      const updatedJob = await apiClient.resumeJob(jobId)
      setJobs(prev => Array.isArray(prev) ? prev.map(job => job.id === jobId ? updatedJob : job) : [updatedJob])
      return updatedJob
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Resume failed'
      setError(errorMessage)
      throw new Error(errorMessage)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  // Poll for job updates every 5 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      if (Array.isArray(jobs)) {
        const hasProcessingJobs = jobs.some(job => 
          job.status === 'pending' || job.status === 'processing'
        )
        
        if (hasProcessingJobs) {
          fetchJobs()
        }
        
        // Check for stuck jobs (processing for more than 3 minutes)
        const now = new Date()
        const stuckJobs = jobs.filter(job => {
          if (job.status !== 'processing' && job.status !== 'pending') return false
          
          const jobTime = new Date(job.updated_at || job.created_at)
          const timeDiff = now.getTime() - jobTime.getTime()
          return timeDiff > 180000 // 3 minutes
        })
        
        if (stuckJobs.length > 0) {
          console.warn('Detected stuck jobs:', stuckJobs.map(j => j.id))
          // Call backend to mark stuck jobs as failed
          try {
            await apiClient.checkStuckJobs()
            // Refresh jobs to get updated status
            fetchJobs()
          } catch (error) {
            console.error('Failed to check stuck jobs:', error)
            // If the endpoint is not available, just refresh jobs to get updated status
            // The backend might have already marked them as failed
            fetchJobs()
          }
        }
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [jobs, fetchJobs])

  return {
    jobs,
    loading,
    error,
    uploadEmail,
    resumeJob,
    refetch: fetchJobs,
  }
}

export function useJob(jobId: number) {
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchJob = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getJob(jobId)
      setJob(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    if (jobId) {
      fetchJob()
    }
  }, [jobId, fetchJob])

  // Poll for job updates if job is still processing
  useEffect(() => {
    if (!job || (job.status !== 'pending' && job.status !== 'processing')) {
      return
    }

    const interval = setInterval(() => {
      fetchJob()
    }, 3000)

    return () => clearInterval(interval)
  }, [job, fetchJob])

  return {
    job,
    loading,
    error,
    refetch: fetchJob,
  }
}
