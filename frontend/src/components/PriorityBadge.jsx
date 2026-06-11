const styles = {
  low:    'bg-slate-100 text-slate-600',
  medium: 'bg-yellow-100 text-yellow-700',
  high:   'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
}

export default function PriorityBadge({ priority }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${styles[priority] || 'bg-slate-100 text-slate-600'}`}>
      {priority}
    </span>
  )
}
