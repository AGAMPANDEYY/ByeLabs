'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { 
  Inbox, 
  FileText, 
  BarChart3, 
  Settings, 
  User,
  Menu,
  X,
  ChevronDown,
  Building2,
  Users,
  BookOpen,
  Handshake
} from 'lucide-react'
import { useState } from 'react'

const mainNavigation = [
  { name: 'Roster Table', href: '/inbox', icon: Inbox },
  { name: 'Exports', href: '/exports', icon: FileText },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
]

const companyNavigation = [
  { 
    name: 'Company', 
    href: '#', 
    icon: Building2,
    dropdown: [
      { name: 'About Us', href: '/about' },
      { name: 'Leadership', href: '/leadership' },
      { name: 'Careers', href: '/careers' },
      { name: 'Press', href: '/press' },
    ]
  },
  { 
    name: 'Our Solutions', 
    href: '#', 
    icon: Users,
    dropdown: [
      { name: 'MCheck Roster Automation', href: '/' },
      { name: 'Provider Data Management', href: '/solutions/provider-data' },
      { name: 'Network Analytics', href: '/solutions/analytics' },
      { name: 'Compliance Tools', href: '/solutions/compliance' },
    ]
  },
  { 
    name: 'Resources', 
    href: '#', 
    icon: BookOpen,
    dropdown: [
      { name: 'Documentation', href: '/docs' },
      { name: 'API Reference', href: '/api' },
      { name: 'Tutorials', href: '/tutorials' },
      { name: 'Support', href: '/support' },
    ]
  },
  { 
    name: 'Partnerships', 
    href: '/partnerships', 
    icon: Handshake,
  },
]

export function AppNavbar() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 w-full">
      <div className="w-full px-6 lg:px-8">
        <div className="flex h-20 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-primary-600 text-3xl">Hi</span>
              <span className="font-bold text-gray-900 text-3xl">Labs</span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {/* Company Navigation with Dropdowns */}
            {companyNavigation.map((item) => (
              <div key={item.name} className="relative">
                {item.dropdown ? (
                  <div
                    className="flex items-center space-x-1 cursor-pointer"
                    onMouseEnter={() => setOpenDropdown(item.name)}
                    onMouseLeave={() => setOpenDropdown(null)}
                  >
                    <span className={cn(
                      "font-medium text-lg transition-colors",
                      item.name === 'Our Solutions' 
                        ? "text-primary-600" 
                        : "text-gray-700 hover:text-primary-600"
                    )}>
                      {item.name}
                    </span>
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                    
                    {/* Dropdown Menu */}
                    {openDropdown === item.name && (
                      <div className="absolute top-full left-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                        {item.dropdown.map((dropdownItem) => (
                          <Link
                            key={dropdownItem.name}
                            href={dropdownItem.href}
                            className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-primary-600"
                          >
                            {dropdownItem.name}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <Link
                    href={item.href}
                    className="text-gray-700 hover:text-primary-600 font-medium text-lg"
                  >
                    {item.name}
                  </Link>
                )}
              </div>
            ))}
            
            {/* Analytics Link */}
            <Link
              href="/analytics"
              className="text-gray-700 hover:text-primary-600 font-medium text-lg"
            >
              Analytics
            </Link>
          </div>

          {/* Right Side - Book Demo Button and User Menu */}
          <div className="hidden md:flex items-center space-x-4">
            <Button className="btn-gradient">
              Book a Demo
            </Button>
            <Button variant="ghost" size="icon">
              <User className="w-5 h-5" />
            </Button>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 py-4">
            <div className="flex flex-col space-y-2">
              {/* Company Navigation */}
              {companyNavigation.map((item) => (
                <div key={item.name}>
                  <div className="flex items-center justify-between px-4 py-2">
                    <span className="text-gray-700 font-medium">{item.name}</span>
                    {item.dropdown && (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    )}
                  </div>
                  {item.dropdown && (
                    <div className="ml-4 space-y-1">
                      {item.dropdown.map((dropdownItem) => (
                        <Link
                          key={dropdownItem.name}
                          href={dropdownItem.href}
                          className="block px-4 py-2 text-sm text-gray-600 hover:text-primary-600"
                          onClick={() => setMobileMenuOpen(false)}
                        >
                          {dropdownItem.name}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              
              {/* Analytics Link */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                <Link
                  href="/analytics"
                  className={cn(
                    'flex items-center space-x-2 px-4 py-3 rounded-xl text-sm font-medium transition-colors',
                    pathname === '/analytics'
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  )}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Analytics</span>
                </Link>
              </div>
              
              {/* Main Navigation */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                {mainNavigation.map((item) => {
                  const isActive = pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={cn(
                        'flex items-center space-x-2 px-4 py-3 rounded-xl text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary-100 text-primary-700'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      )}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <item.icon className="w-4 h-4" />
                      <span>{item.name}</span>
                    </Link>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}