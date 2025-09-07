const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Job {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'error' | 'needs_review' | 'ready' | 'failed' | 'cancelled'
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
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
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

    const response = await fetch(`${this.baseUrl}/ingest`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`)
    }

    const result = await response.json()
    // The ingest endpoint returns job_id, not job object
    // We need to fetch the full job details
    return this.getJob(result.job_id)
  }

  async resumeJob(jobId: number): Promise<Job> {
    return this.request<Job>(`/jobs/${jobId}/process`, {
      method: 'POST',
    })
  }

  // Export Management
  async getJobExports(jobId: number): Promise<Export[]> {
    return this.request<Export[]>(`/jobs/${jobId}/exports`)
  }

  async createExport(jobId: number): Promise<Export> {
    return this.request<Export>(`/jobs/${jobId}/export`, {
      method: 'POST',
    })
  }

  async downloadExport(exportId: number): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/exports/${exportId}/download`)
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }
    
    return await response.blob()
  }

  // Analytics
  async getAnalytics(): Promise<AnalyticsData> {
    return this.request<AnalyticsData>('/analytics')
  }

  // Health Check
  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health')
  }

}

export const apiClient = new ApiClient()
export default apiClient