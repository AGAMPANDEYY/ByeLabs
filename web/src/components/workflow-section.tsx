'use client'

import { 
  ArrowRight, 
  ArrowDown, 
  FileText, 
  Settings, 
  CheckCircle, 
  MessageSquare, 
  Database,
  DollarSign,
  Calendar,
  HelpCircle,
  ArrowDownCircle,
  Sparkles,
  Cog,
  Shield
} from 'lucide-react'

const workflowSteps = [
  {
    id: 1,
    title: "Provider Roster Submission",
    icon: FileText,
    bgColor: "bg-white",
    textColor: "text-gray-900",
    iconColor: "text-orange-500",
    iconBg: "bg-orange-100",
    arrow: "down",
    details: []
  },
  {
    id: 2,
    title: "HiLabs Roster Automation Ingestion",
    icon: Settings,
    bgColor: "bg-primary-600",
    textColor: "text-white",
    iconColor: "text-white",
    iconBg: "bg-white/20",
    arrow: "right",
    details: []
  },
  {
    id: 3,
    title: "Roster Standardization",
    icon: Cog,
    bgColor: "bg-white",
    textColor: "text-gray-900",
    iconColor: "text-orange-500",
    iconBg: "bg-orange-100",
    arrow: "right",
    details: [
      { text: "260+ data elements standardized...", icon: Cog },
      { text: "Critical fields such as complete address...", icon: Shield }
    ]
  },
  {
    id: 4,
    title: "Business Rules Processing",
    icon: Sparkles,
    bgColor: "bg-white",
    textColor: "text-gray-900",
    iconColor: "text-orange-500",
    iconBg: "bg-orange-100",
    arrow: "right",
    details: [
      { text: "Network and Pricing", icon: DollarSign },
      { text: "Directory Suppression", icon: ArrowDownCircle },
      { text: "Effective dates, and more", icon: Calendar }
    ]
  },
  {
    id: 5,
    title: "Data Validation Checks",
    icon: CheckCircle,
    bgColor: "bg-white",
    textColor: "text-gray-900",
    iconColor: "text-orange-500",
    iconBg: "bg-orange-100",
    arrow: "right",
    details: [
      { text: "Missing provider inputs", icon: HelpCircle, border: true },
      { text: "Missing health-plan inputs", icon: HelpCircle, border: true },
      { text: "Complete records", icon: CheckCircle, border: true }
    ]
  },
  {
    id: 6,
    title: "Payer-to-Provider Feedback",
    icon: MessageSquare,
    bgColor: "bg-white",
    textColor: "text-gray-900",
    iconColor: "text-orange-500",
    iconBg: "bg-orange-100",
    arrow: "down",
    details: [
      { text: "Validated insights and reporting", icon: MessageSquare }
    ]
  },
  {
    id: 7,
    title: "Provider Database Update",
    icon: Database,
    bgColor: "bg-primary-600",
    textColor: "text-white",
    iconColor: "text-white",
    iconBg: "bg-white/20",
    arrow: null,
    details: [
      { text: "95% Auto-Adjudication Achieved", icon: CheckCircle, highlight: true },
      { text: "Integration with PDM", icon: Database }
    ]
  }
]

export function WorkflowSection() {
  return (
    <section className="bg-gradient-to-br from-blue-50 via-blue-100 to-indigo-100 py-12">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Description section */}
        <div className="text-center mb-12">
          <h3 className="text-2xl font-bold text-gray-900 max-w-4xl mx-auto mb-8 leading-relaxed">
            Advanced Multi-Agent AI & NLP Algorithms Power Intelligent Roster Automation with Seamless Data Processing & Validation
          </h3>
          
          {/* Multi-Agentic Highlight Box */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-8 text-white max-w-4xl mx-auto">
            <div className="flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 mr-3" />
              <h3 className="text-2xl font-bold">Multi-Agentic AI Pipeline</h3>
            </div>
            <p className="text-lg text-blue-100 mb-4">
              Our sophisticated multi-agent system orchestrates intelligent data processing through specialized AI agents:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-green-300 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-white">Intake & Classification</h4>
                  <p className="text-blue-100 text-sm">Automated email parsing and content classification</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-green-300 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-white">Rule-Based Extraction</h4>
                  <p className="text-blue-100 text-sm">Intelligent data extraction with VLM assistance</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-green-300 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-white">Data Normalization</h4>
                  <p className="text-blue-100 text-sm">Standardized formatting and validation</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <CheckCircle className="w-5 h-5 text-green-300 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-white">Quality Assurance</h4>
                  <p className="text-blue-100 text-sm">Comprehensive validation and error detection</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl lg:text-5xl font-bold text-gray-900">
            BEYOND ROSTER MANAGEMENT: HOW OUR SOLUTION STANDS APART
          </h2>
        </div>

        {/* Workflow Steps */}
        <div className="relative">
          {/* Desktop Layout */}
          <div className="hidden lg:block">
            <div className="grid grid-cols-7 gap-4 items-start">
              {workflowSteps.map((step, index) => (
                <div key={step.id} className="relative">
                  {/* Step Card */}
                  <div className={`${step.bgColor} ${step.textColor} p-6 rounded-2xl shadow-lg border border-gray-200 min-h-[200px] flex flex-col`}>
                    {/* Icon */}
                    <div className={`${step.iconBg} ${step.iconColor} w-12 h-12 rounded-xl flex items-center justify-center mb-4`}>
                      <step.icon className="w-6 h-6" />
                    </div>
                    
                    {/* Title */}
                    <h3 className="font-semibold text-lg mb-4 leading-tight">
                      {step.title}
                    </h3>
                    
                    {/* Details */}
                    {step.details.length > 0 && (
                      <div className="space-y-2 flex-1">
                        {step.details.map((detail, detailIndex) => (
                          <div 
                            key={detailIndex} 
                            className={`flex items-start space-x-2 text-sm ${
                              detail.border ? 'border border-dashed border-gray-300 p-2 rounded' : ''
                            } ${detail.highlight ? 'font-semibold' : ''}`}
                          >
                            <detail.icon className={`w-4 h-4 mt-0.5 ${step.iconColor}`} />
                            <span>{detail.text}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {/* Arrow */}
                  {step.arrow && (
                    <div className="absolute top-1/2 transform -translate-y-1/2 z-10">
                      {step.arrow === 'right' && (
                        <div className="flex items-center">
                          <ArrowRight className="w-8 h-8 text-white" />
                        </div>
                      )}
                      {step.arrow === 'down' && (
                        <div className="flex items-center">
                          <ArrowDown className="w-8 h-8 text-white" />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Mobile Layout */}
          <div className="lg:hidden space-y-6">
            {workflowSteps.map((step, index) => (
              <div key={step.id} className="relative">
                {/* Step Card */}
                <div className={`${step.bgColor} ${step.textColor} p-6 rounded-2xl shadow-lg border border-gray-200`}>
                  {/* Icon */}
                  <div className={`${step.iconBg} ${step.iconColor} w-12 h-12 rounded-xl flex items-center justify-center mb-4`}>
                    <step.icon className="w-6 h-6" />
                  </div>
                  
                  {/* Title */}
                  <h3 className="font-semibold text-lg mb-4 leading-tight">
                    {step.title}
                  </h3>
                  
                  {/* Details */}
                  {step.details.length > 0 && (
                    <div className="space-y-2">
                      {step.details.map((detail, detailIndex) => (
                        <div 
                          key={detailIndex} 
                          className={`flex items-start space-x-2 text-sm ${
                            detail.border ? 'border border-dashed border-gray-300 p-2 rounded' : ''
                          } ${detail.highlight ? 'font-semibold' : ''}`}
                        >
                          <detail.icon className={`w-4 h-4 mt-0.5 ${step.iconColor}`} />
                          <span>{detail.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* Arrow */}
                {step.arrow && index < workflowSteps.length - 1 && (
                  <div className="flex justify-center my-4">
                    {step.arrow === 'right' && (
                      <ArrowDown className="w-8 h-8 text-white" />
                    )}
                    {step.arrow === 'down' && (
                      <ArrowDown className="w-8 h-8 text-white" />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
