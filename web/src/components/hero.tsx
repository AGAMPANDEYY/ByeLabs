'use client'

import { Button } from '@/components/ui/button'
import { Upload, Inbox, CheckCircle, Table, Zap } from 'lucide-react'
import { useRef } from 'react'

export function Hero() {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
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
        // Redirect to job detail page
        window.location.href = `/jobs/${result.job_id}`
      } else {
        alert('Upload failed. Please try again.')
      }
    } catch (error) {
      console.error('Upload error:', error)
      alert('Upload failed. Please try again.')
    }
  }

  return (
    <div className="relative bg-hero-gradient overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-20">
        <div 
          className="w-full h-full"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Ccircle cx='30' cy='30' r='2'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            backgroundRepeat: 'repeat'
          }}
        />
      </div>
      
      <div className="relative container-custom py-24 lg:py-32">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left Content */}
          <div className="text-white">
            <h1 className="text-5xl lg:text-6xl font-bold leading-tight mb-6">
              MCheck-style
              <br />
              <span className="text-blue-200">Roster Automation</span>
            </h1>
            
            <p className="text-xl text-blue-100 mb-8 leading-relaxed">
              Touchless end-to-end roster processing with AI. Automated roster ingestion, 
              standardization, and data quality checks for greater efficiency and better provider relations.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <Button
                variant="gradient"
                size="lg"
                className="bg-white text-primary-600 hover:bg-blue-50 font-semibold"
                onClick={() => window.location.href = '/inbox'}
              >
                <Inbox className="w-5 h-5 mr-2" />
                Open Inbox
              </Button>
              
              <Button
                variant="outline"
                size="lg"
                className="border-white text-white hover:bg-white hover:text-primary-600 font-semibold"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-5 h-5 mr-2" />
                Upload .eml
              </Button>
              
              <input
                ref={fileInputRef}
                type="file"
                accept=".eml"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>
          </div>
          
          {/* Right Illustration */}
          <div className="flex justify-center lg:justify-end">
            <div className="relative">
              {/* Main Card */}
              <div className="bg-white rounded-3xl p-8 shadow-soft-lg max-w-sm">
                <div className="flex items-center justify-center mb-6">
                  <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center">
                    <Table className="w-8 h-8 text-primary-600" />
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="h-3 bg-gray-200 rounded-full"></div>
                  <div className="h-3 bg-gray-200 rounded-full w-3/4"></div>
                  <div className="h-3 bg-gray-200 rounded-full w-1/2"></div>
                </div>
                
                <div className="mt-6 flex items-center justify-between">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  </div>
                  <CheckCircle className="w-6 h-6 text-green-500" />
                </div>
              </div>
              
              {/* Floating Elements */}
              <div className="absolute -top-4 -right-4 bg-accent-500 text-white p-3 rounded-2xl shadow-soft-lg">
                <Zap className="w-6 h-6" />
              </div>
              
              <div className="absolute -bottom-4 -left-4 bg-green-500 text-white p-3 rounded-2xl shadow-soft-lg">
                <CheckCircle className="w-6 h-6" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function HowItWorks() {
  const steps = [
    {
      icon: Upload,
      title: 'Upload Roster',
      description: 'Send your provider roster via email or upload .eml files directly to our secure inbox.',
    },
    {
      icon: Zap,
      title: 'AI Processing',
      description: 'Our multi-agent pipeline automatically extracts, normalizes, and validates provider data.',
    },
    {
      icon: CheckCircle,
      title: 'Export Excel',
      description: 'Download standardized Excel files with the exact schema you need for your systems.',
    },
  ]

  return (
    <div className="py-24 bg-gray-50">
      <div className="container-custom">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            How it works
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Three simple steps to transform your provider roster management
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, index) => (
            <div key={index} className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <step.icon className="w-8 h-8 text-primary-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-3">
                {step.title}
              </h3>
              <p className="text-gray-600 leading-relaxed">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
