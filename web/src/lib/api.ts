const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Job {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'error' | 'needs_review'
  created_at: string
  updated_at: string
  email?: {
    id: number
    from_addr: string
    subject: string
    received_at: string
  }
  current_version_id?: number
  email_subject?: string
  email_from?: string
  total_records?: number
  processed_records?: number
  error_message?: string
  // Legacy fields for backward compatibility
  subject?: string
  from_addr?: string
  // Job details fields
  artifacts?: {
    raw_email?: string
    exports?: Export[]
  }
  current_version?: {
    id: number
    author: string
    reason: string
    created_at: string
    record_count: number
  }
  issues_summary?: {
    error: number
    warning: number
    info: number
  }
  issues_count?: number
}

export interface AnalyticsData {
  totalJobs: number
  completedJobs: number
  pendingJobs: number
  errorJobs: number
  avgProcessingTime: number
  totalExports: number
  successRate: number
}

export interface Export {
  id: number
  job_id: number
  created_at: string
  object_key?: string
  filename?: string
  status: 'pending' | 'completed' | 'error'
  version_id?: number
  file_uri?: string
  checksum?: string
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    timeoutMs: number = 30000
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: controller.signal,
      ...options,
    }

    try {
      const response = await fetch(url, config)
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(`Request timeout after ${timeoutMs}ms`)
      }
      console.error(`API request failed for ${endpoint}:`, error)
      throw error
    }
  }

  // Job Management
  async getJobs(): Promise<Job[]> {
    const response = await this.request<{jobs: Job[], total: number, skip: number, limit: number, has_more: boolean}>('/jobs')
    return response.jobs
  }

  async getJob(jobId: number): Promise<Job> {
    return this.request<Job>(`/jobs/${jobId}`)
  }

  async uploadEmail(file: File): Promise<Job> {
    const formData = new FormData()
    formData.append('file', file)

    // Create abort controller for upload timeout (2 minutes)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 120000)

    try {
      const response = await fetch(`${this.baseUrl}/ingest`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`)
      }

      const result = await response.json()
      // The ingest endpoint returns job_id, not job object
      // We need to fetch the full job details
      return this.getJob(result.job_id)
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Upload timeout after 2 minutes')
      }
      throw error
    }
  }

  async resumeJob(jobId: number): Promise<Job> {
    return this.request<Job>(`/jobs/${jobId}/process`, {
      method: 'POST',
    }, 180000) // 3 minutes timeout for processing
  }

  // Export Management
  async getJobExports(jobId: number): Promise<Export[]> {
    return this.request<Export[]>(`/jobs/${jobId}/exports`)
  }

  async createExport(jobId: number): Promise<Export> {
    return this.request<Export>(`/jobs/${jobId}/export`, {
      method: 'POST',
    }, 60000) // 1 minute timeout for export creation
  }

  async downloadExport(exportId: number): Promise<Blob> {
    // Create abort controller for download timeout (30 seconds)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000)

    try {
      const response = await fetch(`${this.baseUrl}/exports/${exportId}/download`, {
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`)
      }

      return await response.blob()
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Download timeout after 30 seconds')
      }
      throw error
    }
  }

  // Analytics
  async getAnalytics(): Promise<AnalyticsData> {
    return this.request<AnalyticsData>('/analytics')
  }

  // Health Check
  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health')
  }

  // Timeout Management
  async checkStuckJobs(): Promise<{
    message: string
    stuck_jobs_found: number
    jobs_updated: number
    cutoff_time: string
  }> {
    return this.request<{
      message: string
      stuck_jobs_found: number
      jobs_updated: number
      cutoff_time: string
    }>('/jobs/check-timeouts', {
      method: 'POST',
    })
  }
}

export const apiClient = new ApiClient()
export default apiClient