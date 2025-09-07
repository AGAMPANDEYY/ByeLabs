'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useJobs } from '@/hooks/useJobs'

interface FileUploadProps {
  onUploadSuccess?: (jobId: number) => void
  onUploadError?: (error: string) => void
}

export function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { uploadEmail } = useJobs()

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.eml')) {
      setErrorMessage('Please select a .eml file')
      setUploadStatus('error')
      onUploadError?.('Invalid file type. Please select a .eml file.')
      return
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB limit
      setErrorMessage('File size too large. Please select a file smaller than 10MB.')
      setUploadStatus('error')
      onUploadError?.('File size too large.')
      return
    }

    setIsUploading(true)
    setUploadStatus('idle')
    setErrorMessage('')

    try {
      const job = await uploadEmail(file)
      setUploadStatus('success')
      onUploadSuccess?.(job.id)
      
      // Reset status after 3 seconds
      setTimeout(() => {
        setUploadStatus('idle')
      }, 3000)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed'
      setErrorMessage(message)
      setUploadStatus('error')
      onUploadError?.(message)
    } finally {
      setIsUploading(false)
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="w-full">
      <input
        ref={fileInputRef}
        type="file"
        accept=".eml"
        onChange={handleFileSelect}
        className="hidden"
        disabled={isUploading}
      />
      
      <button
        onClick={handleClick}
        disabled={isUploading}
        className={`
          w-full flex items-center justify-center space-x-2 px-6 py-4 rounded-xl border-2 border-dashed transition-all duration-200
          ${isUploading 
            ? 'border-blue-300 bg-blue-50 cursor-not-allowed' 
            : uploadStatus === 'success'
            ? 'border-green-300 bg-green-50'
            : uploadStatus === 'error'
            ? 'border-red-300 bg-red-50'
            : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50'
          }
        `}
      >
        {isUploading ? (
          <>
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
            <span className="text-blue-600 font-medium">Uploading...</span>
          </>
        ) : uploadStatus === 'success' ? (
          <>
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            <span className="text-green-600 font-medium">Upload Successful!</span>
          </>
        ) : uploadStatus === 'error' ? (
          <>
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="text-red-600 font-medium">Upload Failed</span>
          </>
        ) : (
          <>
            <Upload className="w-5 h-5 text-gray-600" />
            <span className="text-gray-600 font-medium">Upload .eml file</span>
          </>
        )}
      </button>

      {errorMessage && (
        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-600" />
            <span className="text-sm text-red-600">{errorMessage}</span>
          </div>
        </div>
      )}

      {uploadStatus === 'success' && (
        <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            <span className="text-sm text-green-600">File uploaded successfully! Processing started.</span>
          </div>
        </div>
      )}
    </div>
  )
}
