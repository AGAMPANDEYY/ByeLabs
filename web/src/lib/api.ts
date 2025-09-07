const API_BASE_URL = 'http://localhost:8000'

export interface Job {
  id: number
  status: 'pending' | 'processing' | 'needs_review' | 'ready' | 'failed' | 'cancelled'
  created_at: string
  updated_at: string
  subject?: string
  from_addr?: string
  to_addr?: string
  current_version_id?: number
  issues_count?: number
  vlm_used?: boolean
}

export interface JobDetail extends Job {
  email_metadata: {
    message_id: string
    from_addr: string
    to_addr: string
    subject: string
    received_at: string
  }
  artifacts: Array<{
    type: string
    document_type: string
    content?: string
    uri?: string
    filename?: string
    content_type?: string
    size?: number
  }>
  issues: Array<{
    id: number
    row_idx?: number
    field?: string
    level: 'error' | 'warning' | 'info'
    message: string
  }>
  rows?: Array<{
    row_idx: number
    data: Record<string, any>
  }>
}

export interface Version {
  id: number
  job_id: number
  parent_version_id?: number
  author: string
  reason: string
  created_at: string
}

export interface Export {
  id: number
  job_id: number
  version_id: number
  file_uri: string
  checksum: string
  created_at: string
}

export interface AnalyticsSummary {
  jobs_today: number
  success_rate: number
  avg_processing_time: number
  vlm_usage_rate: number
  top_errors: Array<{
    error: string
    count: number
  }>
}

// API Helper Functions
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API Error: ${response.status} - ${error}`)
  }

  return response.json()
}

// Job API
export async function getJobs(): Promise<Job[]> {
  return apiRequest<Job[]>('/jobs')
}

export async function getJob(id: number): Promise<JobDetail> {
  return apiRequest<JobDetail>(`/jobs/${id}`)
}

export async function processJob(id: number, forceVlm = false): Promise<{ job_id: number }> {
  const params = forceVlm ? '?force_vlm=true' : ''
  return apiRequest<{ job_id: number }>(`/jobs/${id}/process${params}`, {
    method: 'POST',
  })
}

export async function ingestEml(file: File): Promise<{ job_id: number }> {
  const formData = new FormData()
  formData.append('eml', file)
  
  const response = await fetch(`${API_BASE_URL}/ingest`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Upload Error: ${response.status} - ${error}`)
  }

  return response.json()
}

// Version API
export async function getJobVersions(jobId: number): Promise<Version[]> {
  return apiRequest<Version[]>(`/jobs/${jobId}/versions`)
}

export async function rollbackVersion(jobId: number, versionId: number): Promise<void> {
  return apiRequest<void>(`/jobs/${jobId}/versions/${versionId}/rollback`, {
    method: 'POST',
  })
}

// Edit API
export async function editCell(
  jobId: number,
  rowIdx: number,
  field: string,
  value: string
): Promise<{ version_id: number }> {
  return apiRequest<{ version_id: number }>(`/jobs/${jobId}/edit`, {
    method: 'POST',
    body: JSON.stringify({ row_idx: rowIdx, field, value }),
  })
}

// Export API
export async function exportJob(jobId: number): Promise<{ export_id: number; file_uri: string }> {
  return apiRequest<{ export_id: number; file_uri: string }>(`/jobs/${jobId}/export`, {
    method: 'POST',
  })
}

export async function getExports(): Promise<Export[]> {
  return apiRequest<Export[]>('/exports')
}

export async function downloadExport(exportId: number): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/exports/${exportId}/download`)
  
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Download Error: ${response.status} - ${error}`)
  }

  return response.blob()
}

// Analytics API
export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  try {
    return apiRequest<AnalyticsSummary>('/analytics/summary')
  } catch (error) {
    // Fallback to parsing metrics if analytics endpoint doesn't exist
    return getMetricsSummary()
  }
}

async function getMetricsSummary(): Promise<AnalyticsSummary> {
  const response = await fetch(`${API_BASE_URL}/metrics`)
  const text = await response.text()
  
  // Parse Prometheus metrics (simplified)
  const lines = text.split('\n')
  const jobsTotal = lines.find(line => line.startsWith('jobs_total'))?.split(' ')[1] || '0'
  const jobsSuccess = lines.find(line => line.startsWith('jobs_success_total'))?.split(' ')[1] || '0'
  
  return {
    jobs_today: parseInt(jobsTotal),
    success_rate: jobsTotal === '0' ? 0 : (parseInt(jobsSuccess) / parseInt(jobsTotal)) * 100,
    avg_processing_time: 0,
    vlm_usage_rate: 0,
    top_errors: [],
  }
}
