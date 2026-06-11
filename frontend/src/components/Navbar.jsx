import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Navbar() {
  const navigate = useNavigate()
  const email = localStorage.getItem('email') || ''

  async function handleLogout() {
    try { await api.logout() } catch {}
    localStorage.removeItem('token')
    localStorage.removeItem('email')
    navigate('/login')
  }

  return (
    <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
      <button
        onClick={() => navigate('/tasks')}
        className="text-indigo-600 font-bold text-lg tracking-tight hover:text-indigo-700"
      >
        ⬡ task-flow
      </button>
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-500 hidden sm:block">{email}</span>
        <button
          onClick={handleLogout}
          className="text-sm text-slate-600 hover:text-slate-900 font-medium"
        >
          Logout
        </button>
      </div>
    </nav>
  )
}
