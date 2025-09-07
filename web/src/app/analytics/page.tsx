'use client'

import { useState, useEffect } from 'react'
import { useAnalytics } from '@/hooks/useAnalytics'
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  FileText, 
  Clock, 
  CheckCircle,
  AlertCircle,
  Download,
  Calendar
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface AnalyticsData {
  totalJobs: number
  completedJobs: number
  pendingJobs: number
  errorJobs: number
  avgProcessingTime: number
  totalExports: number
  successRate: number
}

interface ChartData {
  date: string
  jobs: number
  exports: number
}

export default function AnalyticsPage() {
  const { analytics, loading } = useAnalytics()
  const [chartData, setChartData] = useState<ChartData[]>([])

  useEffect(() => {
    // Mock chart data for now - can be replaced with real API call
    setChartData([
      { date: '2024-01-01', jobs: 45, exports: 42 },
      { date: '2024-01-02', jobs: 52, exports: 48 },
      { date: '2024-01-03', jobs: 38, exports: 35 },
      { date: '2024-01-04', jobs: 61, exports: 58 },
      { date: '2024-01-05', jobs: 47, exports: 44 },
      { date: '2024-01-06', jobs: 39, exports: 36 },
      { date: '2024-01-07', jobs: 55, exports: 52 },
    ])
  }, [])

  const metrics = [
    {
      title: 'Total Jobs',
      value: analytics.totalJobs.toLocaleString(),
      icon: FileText,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
      change: '+12%',
      changeType: 'positive'
    },
    {
      title: 'Success Rate',
      value: `${analytics.successRate}%`,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
      change: '+2.1%',
      changeType: 'positive'
    },
    {
      title: 'Avg Processing Time',
      value: `${analytics.avgProcessingTime}m`,
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-100',
      change: '-0.3m',
      changeType: 'positive'
    },
    {
      title: 'Total Exports',
      value: analytics.totalExports.toLocaleString(),
      icon: Download,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
      change: '+8%',
      changeType: 'positive'
    }
  ]

  const statusData = [
    { label: 'Completed', value: analytics.completedJobs, color: 'bg-green-500' },
    { label: 'Pending', value: analytics.pendingJobs, color: 'bg-yellow-500' },
    { label: 'Errors', value: analytics.errorJobs, color: 'bg-red-500' }
  ]

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white p-6 rounded-2xl shadow-lg">
                <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
                <div className="h-8 bg-gray-200 rounded w-3/4"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
          <p className="text-gray-600 mt-2">
            Monitor your roster processing performance and insights
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Button variant="outline" className="flex items-center space-x-2">
            <Calendar className="w-4 h-4" />
            <span>Last 30 days</span>
          </Button>
          <Button className="btn-primary">
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {metrics.map((metric, index) => (
          <div key={index} className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">{metric.title}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{metric.value}</p>
                <p className={cn(
                  "text-sm mt-1",
                  metric.changeType === 'positive' ? 'text-green-600' : 'text-red-600'
                )}>
                  {metric.change} from last month
                </p>
              </div>
              <div className={cn("p-3 rounded-xl", metric.bgColor)}>
                <metric.icon className={cn("w-6 h-6", metric.color)} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        {/* Job Status Chart */}
        <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Job Status Distribution</h3>
          <div className="space-y-4">
            {statusData.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={cn("w-3 h-3 rounded-full", item.color)}></div>
                  <span className="text-sm font-medium text-gray-700">{item.label}</span>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="w-32 bg-gray-200 rounded-full h-2">
                    <div 
                      className={cn("h-2 rounded-full", item.color)}
                      style={{ width: `${(item.value / analytics.totalJobs) * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium text-gray-900 w-12 text-right">
                    {item.value}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Processing Time Chart */}
        <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Processing Trends</h3>
          <div className="space-y-4">
            {chartData.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.date}</span>
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    <span className="text-sm text-gray-700">Jobs: {item.jobs}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm text-gray-700">Exports: {item.exports}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {[
              { action: 'Job completed', file: 'roster_2024_01.xlsx', time: '2 minutes ago', status: 'success' },
              { action: 'Export generated', file: 'provider_data_export.xlsx', time: '5 minutes ago', status: 'success' },
              { action: 'Job failed', file: 'corrupted_roster.eml', time: '12 minutes ago', status: 'error' },
              { action: 'Job completed', file: 'network_update.xlsx', time: '18 minutes ago', status: 'success' },
              { action: 'Export generated', file: 'compliance_report.xlsx', time: '25 minutes ago', status: 'success' },
            ].map((activity, index) => (
              <div key={index} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-b-0">
                <div className="flex items-center space-x-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    activity.status === 'success' ? 'bg-green-500' : 'bg-red-500'
                  )}></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{activity.action}</p>
                    <p className="text-sm text-gray-600">{activity.file}</p>
                  </div>
                </div>
                <span className="text-sm text-gray-500">{activity.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
