'use client'

import Link from "next/link";
import { Upload, Sparkles, CheckCircle2, BarChart3, TrendingUp, Users, FileText, ArrowRight } from "lucide-react";
import { useAnalytics } from "@/hooks/useAnalytics";
import { FileUpload } from "@/components/file-upload";

export function Hero() {
  const { analytics, loading } = useAnalytics();
  
  const analyticsData = [
    { label: "Total Jobs", value: analytics.totalJobs.toLocaleString(), change: "+12%", icon: FileText, color: "text-blue-400" },
    { label: "Success Rate", value: `${analytics.successRate}%`, change: "+2.1%", icon: CheckCircle2, color: "text-green-400" },
    { label: "Avg Processing", value: `${analytics.avgProcessingTime}m`, change: "-0.3m", icon: TrendingUp, color: "text-orange-400" },
    { label: "Total Exports", value: analytics.totalExports.toLocaleString(), change: "+8%", icon: BarChart3, color: "text-purple-400" }
  ];

  return (
    <section className="relative overflow-hidden">
      <div className="bg-hilabs-hero">
        <div className="mx-auto max-w-7xl px-6 py-20 text-white">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Left Side - Main Content */}
            <div>
              <span className="pill border-white/30 bg-white/10 text-white/90 mb-4">Touchless end-to-end</span>
              <h1 className="text-4xl md:text-6xl font-extrabold leading-tight">
                MCheck-style<br />Roster Automation
              </h1>
              <p className="mt-4 text-lg md:text-xl text-white/90">
                Automated roster ingestion, standardization, and data quality checks for greater efficiency and better provider relations.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link href="/inbox" className="btn-gradient">View Roster Table</Link>
                <div className="w-full sm:w-auto">
                  <FileUpload 
                    onUploadSuccess={(jobId) => {
                      console.log('Upload successful, job ID:', jobId)
                      // Optionally redirect to inbox or show success message
                    }}
                    onUploadError={(error) => {
                      console.error('Upload error:', error)
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Right Side - Analytics and Flow Guide Side by Side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Analytics Preview */}
              <div className="bg-gradient-to-br from-white/95 via-white/90 to-blue-50/80 backdrop-blur-sm rounded-2xl p-5 border border-blue-200/50 shadow-lg">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">System Analytics</h3>
                  <Link href="/analytics" className="flex items-center text-blue-600 hover:text-blue-700 transition-colors">
                    <span className="text-sm mr-1">View More</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
                
                {/* Analytics Grid */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {analyticsData.map((item, index) => (
                    <div key={index} className="bg-gradient-to-br from-white to-blue-50/50 rounded-lg p-3 border border-blue-100 shadow-sm">
                      <div className="flex items-center justify-between mb-1">
                        <item.icon className={`w-4 h-4 ${item.color}`} />
                        <span className="text-xs text-gray-600">{item.change}</span>
                      </div>
                      <div className="text-lg font-bold text-gray-900 mb-1">{item.value}</div>
                      <div className="text-xs text-gray-600">{item.label}</div>
                    </div>
                  ))}
                </div>

                {/* Mini Chart */}
                <div className="bg-gradient-to-br from-white to-blue-50/50 rounded-lg p-3 border border-blue-100 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">Processing Trends</span>
                    <span className="text-xs text-gray-600">Last 7 days</span>
                  </div>
                  <div className="flex items-end space-x-1 h-12">
                    {[65, 78, 82, 75, 88, 92, 85].map((height, index) => (
                      <div key={index} className="flex-1 bg-gradient-to-t from-blue-500 to-blue-300 rounded-t" 
                           style={{ height: `${height}%` }}></div>
                    ))}
                  </div>
                  <div className="flex justify-between text-xs text-gray-600 mt-1">
                    <span>Mon</span>
                    <span>Tue</span>
                    <span>Wed</span>
                    <span>Thu</span>
                    <span>Fri</span>
                    <span>Sat</span>
                    <span>Sun</span>
                  </div>
                </div>
              </div>

              {/* Flow Guide */}
              <div className="bg-gradient-to-br from-white/95 via-white/90 to-green-50/80 backdrop-blur-sm rounded-2xl p-5 border border-green-200/50 shadow-lg">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">How to Use RosterChecker</h3>
                  <Sparkles className="w-5 h-5 text-green-600" />
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">1</div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Upload .eml file here</p>
                      <p className="text-xs text-gray-600">Use the upload button above to process your roster email</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">2</div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Go to "View Roster Table"</p>
                      <p className="text-xs text-gray-600">Click the button to see all processed emails and their status</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">3</div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Click on emails to view details</p>
                      <p className="text-xs text-gray-600">See processing logs, preview data tables, and download Excel files</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-sm font-semibold">✓</div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Preview & Download</p>
                      <p className="text-xs text-gray-600">Preview extracted data and download standardized Excel files</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function HowItWorks() {
  const steps = [
    { icon: <Upload className="h-5 w-5" />, title: "Upload Roster", desc: "Send via email or upload .eml directly to the secure local inbox." },
    { icon: <Sparkles className="h-5 w-5" />, title: "AI Processing", desc: "Multi-agent pipeline extracts, normalizes, and validates data (VLM assist)." },
    { icon: <CheckCircle2 className="h-5 w-5" />, title: "Export to Excel", desc: "Review changes, version/rollback, and download the exact template." },
  ];
  return (
    <section className="mx-auto max-w-7xl px-6 py-16">
      <h2 className="text-2xl md:text-3xl font-bold">How it works</h2>
      <p className="mt-2 text-slate-600">Three simple steps to transform your provider roster management</p>
      <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {steps.map((s, i) => (
          <div key={i} className="card p-6">
            <div className="pill border-slate-200 text-slate-700 mb-4">{s.icon}</div>
            <h3 className="text-lg font-semibold">{s.title}</h3>
            <p className="mt-2 text-slate-600">{s.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
