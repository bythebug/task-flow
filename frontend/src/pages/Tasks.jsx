import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Navbar from '../components/Navbar'
import StatusBadge from '../components/StatusBadge'
import PriorityBadge from '../components/PriorityBadge'

const STATUSES  = ['todo', 'in_progress', 'done', 'cancelled']
const PRIORITIES = ['low', 'medium', 'high', 'urgent']

function Modal({ onClose, onCreated }) {
  const [form, setForm] = useState({ title: '', description: '', status: 'todo', priority: 'medium' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const task = await api.createTask(form)
      onCreated(task)
    } catch (err) {
      setError(err.errors ? Object.values(err.errors)[0] : err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-slate-800">New Task</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Title *</label>
            <input
              required
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              placeholder="What needs to be done?"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea
              rows={3}
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Optional details…"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
              <select
                value={form.status}
                onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Priority</label>
              <select
                value={form.priority}
                onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 font-medium">Cancel</button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {loading ? 'Creating…' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Tasks() {
  const navigate = useNavigate()
  const [tasks, setTasks]         = useState([])
  const [total, setTotal]         = useState(0)
  const [loading, setLoading]     = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [statusFilter, setStatus]   = useState('')
  const [priorityFilter, setPriority] = useState('')

  useEffect(() => {
    fetchTasks()
  }, [statusFilter, priorityFilter])

  async function fetchTasks() {
    setLoading(true)
    try {
      const data = await api.listTasks({ status: statusFilter, priority: priorityFilter })
      setTasks(data.tasks)
      setTotal(data.total)
    } catch (err) {
      if (err.status === 401) navigate('/login')
    } finally {
      setLoading(false)
    }
  }

  function handleCreated(task) {
    setShowModal(false)
    setTasks(prev => [task, ...prev])
    setTotal(t => t + 1)
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">My Tasks</h1>
            <p className="text-sm text-slate-500 mt-0.5">{total} task{total !== 1 ? 's' : ''}</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            <span className="text-lg leading-none">+</span> New Task
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <select
            value={statusFilter}
            onChange={e => setStatus(e.target.value)}
            className="px-3 py-2 border border-slate-300 bg-white rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Statuses</option>
            {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <select
            value={priorityFilter}
            onChange={e => setPriority(e.target.value)}
            className="px-3 py-2 border border-slate-300 bg-white rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Priorities</option>
            {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        {/* Task grid */}
        {loading ? (
          <div className="text-center py-20 text-slate-400">Loading…</div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-slate-400 text-lg mb-4">No tasks yet</p>
            <button
              onClick={() => setShowModal(true)}
              className="text-indigo-600 hover:text-indigo-700 font-medium text-sm"
            >
              Create your first task →
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.map(task => (
              <button
                key={task.id}
                onClick={() => navigate(`/tasks/${task.id}`)}
                className="bg-white border border-slate-200 rounded-xl p-4 text-left hover:border-indigo-300 hover:shadow-md transition-all group"
              >
                <h3 className="font-semibold text-slate-800 text-sm mb-1 line-clamp-2 group-hover:text-indigo-600">
                  {task.title}
                </h3>
                {task.description && (
                  <p className="text-xs text-slate-400 mb-3 line-clamp-2">{task.description}</p>
                )}
                <div className="flex items-center gap-2 flex-wrap mt-auto">
                  <StatusBadge status={task.status} />
                  <PriorityBadge priority={task.priority} />
                  <span className="text-xs text-slate-400 ml-auto">
                    {new Date(task.created_at).toLocaleDateString()}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>

      {showModal && <Modal onClose={() => setShowModal(false)} onCreated={handleCreated} />}
    </div>
  )
}
