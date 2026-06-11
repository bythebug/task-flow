import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import Navbar from '../components/Navbar'
import StatusBadge from '../components/StatusBadge'
import PriorityBadge from '../components/PriorityBadge'

const STATUSES  = ['todo', 'in_progress', 'done', 'cancelled']
const PRIORITIES = ['low', 'medium', 'high', 'urgent']
const PERM_LEVELS = ['view', 'edit', 'delete']

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [task, setTask]               = useState(null)
  const [form, setForm]               = useState({})
  const [saving, setSaving]           = useState(false)
  const [saveMsg, setSaveMsg]         = useState('')
  const [collaborators, setCollabs]   = useState([])
  const [shareEmail, setShareEmail]   = useState('')
  const [shareLevel, setShareLevel]   = useState('view')
  const [sharing, setSharing]         = useState(false)
  const [shareMsg, setShareMsg]       = useState('')
  const [shareError, setShareError]   = useState('')
  const [loading, setLoading]         = useState(true)
  const [deleting, setDeleting]       = useState(false)

  useEffect(() => { load() }, [id])

  async function load() {
    try {
      const [taskData, collabData] = await Promise.all([
        api.getTask(id),
        api.getCollaborators(id).catch(() => ({ collaborators: [] })),
      ])
      setTask(taskData)
      setForm({
        title:       taskData.title,
        description: taskData.description || '',
        status:      taskData.status,
        priority:    taskData.priority,
      })
      setCollabs(collabData.collaborators)
    } catch (err) {
      if (err.status === 401) navigate('/login')
      else navigate('/tasks')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setSaveMsg('')
    try {
      const updated = await api.updateTask(id, form)
      setTask(updated)
      setSaveMsg('Saved!')
      setTimeout(() => setSaveMsg(''), 2000)
    } catch (err) {
      setSaveMsg(err.errors ? Object.values(err.errors)[0] : err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Delete this task?')) return
    setDeleting(true)
    try {
      await api.deleteTask(id)
      navigate('/tasks')
    } catch (err) {
      setSaveMsg(err.message)
      setDeleting(false)
    }
  }

  async function handleShare(e) {
    e.preventDefault()
    setSharing(true)
    setShareMsg('')
    setShareError('')
    try {
      await api.shareTask(id, shareEmail, shareLevel)
      setShareMsg(`Shared with ${shareEmail}`)
      setShareEmail('')
      const data = await api.getCollaborators(id)
      setCollabs(data.collaborators)
    } catch (err) {
      setShareError(err.message)
    } finally {
      setSharing(false)
    }
  }

  async function handleRevoke(userId, email) {
    if (!confirm(`Revoke ${email}'s access?`)) return
    try {
      await api.revokeAccess(id, userId)
      setCollabs(prev => prev.filter(c => c.user_id !== userId))
    } catch (err) {
      setShareError(err.message)
    }
  }

  async function handleUpdatePerm(userId, level) {
    try {
      await api.updatePermission(id, userId, level)
      setCollabs(prev => prev.map(c => c.user_id === userId ? { ...c, permission_level: level } : c))
    } catch (err) {
      setShareError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <div className="text-center py-20 text-slate-400">Loading…</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 py-8">

        <button
          onClick={() => navigate('/tasks')}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-6"
        >
          ← Back to tasks
        </button>

        {/* Edit form */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Task Details</h2>
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Title</label>
              <input
                required
                value={form.title || ''}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
              <textarea
                rows={4}
                value={form.description || ''}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Add more details…"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
                <select
                  value={form.status || ''}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Priority</label>
                <select
                  value={form.priority || ''}
                  onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 text-sm font-medium rounded-lg transition-colors"
              >
                {deleting ? 'Deleting…' : 'Delete Task'}
              </button>
              {saveMsg && (
                <span className={`text-sm ${saveMsg === 'Saved!' ? 'text-green-600' : 'text-red-600'}`}>
                  {saveMsg}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* Share section */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Share Task</h2>

          <form onSubmit={handleShare} className="flex gap-2 mb-4">
            <input
              type="email"
              required
              value={shareEmail}
              onChange={e => setShareEmail(e.target.value)}
              placeholder="colleague@example.com"
              className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <select
              value={shareLevel}
              onChange={e => setShareLevel(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {PERM_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <button
              type="submit"
              disabled={sharing}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
            >
              {sharing ? '…' : 'Share'}
            </button>
          </form>

          {shareMsg   && <p className="text-sm text-green-600 mb-3">{shareMsg}</p>}
          {shareError && <p className="text-sm text-red-600 mb-3">{shareError}</p>}

          {/* Collaborators list */}
          {collaborators.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Collaborators</p>
              {collaborators.map(c => (
                <div key={c.user_id} className="flex items-center gap-3 py-2 border-t border-slate-100">
                  <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 text-xs flex items-center justify-center font-medium">
                    {c.email[0].toUpperCase()}
                  </div>
                  <span className="text-sm text-slate-700 flex-1 truncate">{c.email}</span>
                  <select
                    value={c.permission_level}
                    onChange={e => handleUpdatePerm(c.user_id, e.target.value)}
                    className="px-2 py-1 border border-slate-200 rounded text-xs text-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    {PERM_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                  </select>
                  <button
                    onClick={() => handleRevoke(c.user_id, c.email)}
                    className="text-xs text-red-500 hover:text-red-700 font-medium"
                  >
                    Revoke
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Not shared with anyone yet.</p>
          )}
        </div>

      </main>
    </div>
  )
}
