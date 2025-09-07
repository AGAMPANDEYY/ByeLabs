'use client'

import { useState, useEffect } from 'react'
import { Download, Eye, FileSpreadsheet, AlertCircle, CheckCircle2 } from 'lucide-react'
import { apiClient } from '@/lib/api'

interface ExcelPreviewProps {
  jobId: number
  exportId?: number
  objectKey?: string
  className?: string
}

interface ExcelData {
  headers: string[]
  rows: any[][]
  totalRows: number
}

export function ExcelPreview({ jobId, exportId, objectKey, className = '' }: ExcelPreviewProps) {
  const [excelData, setExcelData] = useState<ExcelData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)

  const loadExcelData = async () => {
    if (!exportId) return

    setLoading(true)
    setError(null)

    try {
      // Download the Excel file
      const blob = await apiClient.downloadExport(exportId)
      
      // Parse Excel data (simplified - in real implementation you'd use a library like xlsx)
      // For now, we'll create mock data based on the expected schema
      const mockData: ExcelData = {
        headers: [
          "Transaction Type",
          "Transaction Attribute", 
          "Effective Date",
          "Term Date",
          "Term Reason",
          "Provider Name",
          "Provider NPI",
          "Provider Specialty",
          "State License",
          "Organization Name",
          "TIN",
          "Group NPI",
          "Complete Address",
          "Phone Number",
          "Fax Number",
          "PPG ID",
          "Line Of Business"
        ],
        rows: [
          ["Term", "Provider Termination", "2024-01-01", "2024-01-31", "Voluntary", "John Smith", "1234567890", "Internal Medicine", "MD12345", "RCHN & RCSSD", "123456789", "987654321", "123 Main St, City, ST 12345", "555-123-4567", "555-123-4568", "PPG001", "Commercial"],
          ["Add", "New Provider", "2024-02-01", "", "", "Jane Doe", "0987654321", "Cardiology", "MD67890", "RCHN & RCSSD", "123456789", "987654321", "456 Oak Ave, City, ST 12345", "555-987-6543", "555-987-6544", "PPG002", "Medicare"]
        ],
        totalRows: 2
      }

      setExcelData(mockData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Excel data')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!exportId) return

    try {
      const blob = await apiClient.downloadExport(exportId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `roster_export_${jobId}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    }
  }

  const togglePreview = () => {
    if (!showPreview && !excelData && exportId) {
      loadExcelData()
    }
    setShowPreview(!showPreview)
  }

  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <FileSpreadsheet className="w-5 h-5 text-green-600" />
          <h3 className="text-lg font-semibold text-gray-900">Excel Export</h3>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={togglePreview}
            disabled={loading}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <Eye className="w-4 h-4 mr-2" />
            {showPreview ? 'Hide Preview' : 'Preview'}
          </button>
          <button
            onClick={handleDownload}
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center">
            <AlertCircle className="w-4 h-4 text-red-600 mr-2" />
            <span className="text-sm text-red-600">{error}</span>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading Excel data...</span>
        </div>
      )}

      {showPreview && excelData && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Preview ({excelData.totalRows} rows)
              </span>
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span className="text-xs text-green-600">Ready for Download</span>
              </div>
            </div>
          </div>
          
          <div className="overflow-x-auto max-h-96">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {excelData.headers.map((header, index) => (
                    <th
                      key={index}
                      className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {excelData.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    {row.map((cell, cellIndex) => (
                      <td
                        key={cellIndex}
                        className="px-3 py-2 text-sm text-gray-900 whitespace-nowrap"
                      >
                        {cell || '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {excelData.totalRows > 10 && (
            <div className="bg-gray-50 px-4 py-2 border-t border-gray-200">
              <p className="text-xs text-gray-500 text-center">
                Showing first 10 rows. Download full file to see all {excelData.totalRows} rows.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Export Status Component
interface ExportStatusProps {
  jobId: number
  className?: string
}

export function ExportStatus({ jobId, className = '' }: ExportStatusProps) {
  const [exports, setExports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadExports = async () => {
      try {
        setLoading(true)
        // This would call the backend endpoint to get exports for the job
        // For now, we'll use mock data
        const mockExports = [
          {
            id: 1,
            job_id: jobId,
            created_at: new Date().toISOString(),
            object_key: `exports/job_${jobId}_export_1.xlsx`,
            filename: `roster_export_${jobId}.xlsx`,
            status: 'completed'
          }
        ]
        setExports(mockExports)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load exports')
      } finally {
        setLoading(false)
      }
    }

    loadExports()
  }, [jobId])

  if (loading) {
    return (
      <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading export status...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`bg-white rounded-lg border border-red-200 p-6 ${className}`}>
        <div className="flex items-center">
          <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
          <span className="text-red-600">{error}</span>
        </div>
      </div>
    )
  }

  if (exports.length === 0) {
    return (
      <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
        <div className="text-center py-4">
          <FileSpreadsheet className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500">No exports available yet</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {exports.map((exportItem) => (
        <ExcelPreview
          key={exportItem.id}
          jobId={jobId}
          exportId={exportItem.id}
        />
      ))}
    </div>
  )
}
