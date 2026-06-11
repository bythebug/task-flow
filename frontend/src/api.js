async function request(method, path, body) {
  const token = localStorage.getItem('token')
  const res = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })

  const data = await res.json()
  if (!res.ok) {
    const err = new Error(data.error || 'Request failed')
    err.status = res.status
    err.errors = data.errors
    throw err
  }
  return data
}

export const api = {
  register: (email, password) =>
    request('POST', '/auth/register', { email, password }),

  login: (email, password) =>
    request('POST', '/auth/login', { email, password }),

  logout: () => request('POST', '/auth/logout'),

  listTasks: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v))
    ).toString()
    return request('GET', `/tasks/${q ? '?' + q : ''}`)
  },

  createTask: (data) => request('POST', '/tasks/', data),
  getTask:    (id)   => request('GET',  `/tasks/${id}`),
  updateTask: (id, data) => request('PUT',    `/tasks/${id}`, data),
  deleteTask: (id)   => request('DELETE', `/tasks/${id}`),

  shareTask:        (id, email, level) =>
    request('POST', `/tasks/${id}/share`, { email, permission_level: level }),
  getCollaborators: (id) =>
    request('GET',  `/tasks/${id}/collaborators`),
  updatePermission: (id, userId, level) =>
    request('PUT',  `/tasks/${id}/permissions/${userId}`, { permission_level: level }),
  revokeAccess:     (id, userId) =>
    request('DELETE', `/tasks/${id}/share/${userId}`),
}
