'use client'

import { useAuth } from './AuthProvider'
import { useRouter } from 'next/navigation'

export default function Navbar() {
  const { user, signOut } = useAuth()
  const router = useRouter()

  return (
    <nav className="bg-white border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2.5"
          >
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">H</span>
            </div>
            <span className="text-gray-900 font-bold text-xl tracking-tight">hotelify</span>
          </button>

          {user && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-400 hidden sm:block">{user.email}</span>
              <button
                onClick={() => { signOut(); router.push('/login') }}
                className="text-sm text-gray-500 hover:text-primary transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
