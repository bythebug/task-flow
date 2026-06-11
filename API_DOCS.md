# task-flow API Reference

Base URL: `http://localhost:5000`

All request bodies are JSON. All responses are JSON. Protected endpoints require:

```
Authorization: Bearer <token>
```

---

## Authentication

### POST /auth/register

Create a new user account.

**Request**
```json
{
  "email": "alice@example.com",
  "password": "Password123"
}
```

**Password rules:** minimum 8 characters, at least one uppercase, one lowercase, one digit.

**Response `201`**
```json
{
  "user_id": 1,
  "message": "Registration successful"
}
```

**Errors**

| Status | Message |
|---|---|
| 400 | `{"error": "Validation failed", "errors": {"email": "Invalid email format"}}` |
| 400 | `{"error": "Validation failed", "errors": {"password": "Must be at least 8 characters"}}` |
| 409 | `{"error": "Email already registered"}` |

---

### POST /auth/login

Exchange credentials for a JWT token.

**Request**
```json
{
  "email": "alice@example.com",
  "password": "Password123"
}
```

**Response `200`**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 86400
}
```

`expires_in` is in seconds (86400 = 24 hours).

**Errors**

| Status | Message |
|---|---|
| 400 | `{"error": "Validation failed", "errors": {"email": "Email and password are required"}}` |
| 401 | `{"error": "Invalid email or password"}` |

---

### POST /auth/logout

Revoke the current token. Requires authentication.

**Response `200`**
```json
{
  "message": "Logged out successfully"
}
```

**Errors**

| Status | Message |
|---|---|
| 401 | `{"error": "Missing or invalid Authorization header"}` |
| 401 | `{"error": "Token has been revoked"}` |

---

## Tasks

### GET /tasks/

List the authenticated user's tasks. Supports pagination and filtering.

**Query Parameters**

| Parameter | Type | Description | Default |
|---|---|---|---|
| `page` | integer | Page number | `1` |
| `limit` | integer | Items per page (max 100) | `20` |
| `status` | string | Filter: `todo`, `in_progress`, `done`, `cancelled` | — |
| `priority` | string | Filter: `low`, `medium`, `high`, `urgent` | — |

**Example**
```
GET /tasks/?page=1&limit=10&status=todo&priority=high
```

**Response `200`**
```json
{
  "tasks": [
    {
      "id": 1,
      "user_id": 1,
      "title": "Write unit tests",
      "description": "Cover all auth endpoints",
      "status": "todo",
      "priority": "high",
      "created_at": "2026-06-11T10:00:00+00:00",
      "updated_at": "2026-06-11T10:00:00+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 10,
  "pages": 1
}
```

> Unfiltered requests are served from Redis cache (5-minute TTL). Filtered requests always hit the database.

---

### POST /tasks/

Create a new task.

**Request**
```json
{
  "title": "Write unit tests",
  "description": "Cover all auth endpoints",
  "status": "todo",
  "priority": "high"
}
```

`title` is required. `status` defaults to `todo`. `priority` defaults to `medium`.

**Valid values**

- `status`: `todo` | `in_progress` | `done` | `cancelled`
- `priority`: `low` | `medium` | `high` | `urgent`

**Response `201`**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "Write unit tests",
  "description": "Cover all auth endpoints",
  "status": "todo",
  "priority": "high",
  "created_at": "2026-06-11T10:00:00+00:00",
  "updated_at": "2026-06-11T10:00:00+00:00"
}
```

**Errors**

| Status | Message |
|---|---|
| 400 | `{"error": "Validation failed", "errors": {"title": "Title is required"}}` |
| 400 | `{"error": "Validation failed", "errors": {"status": "Must be one of: cancelled, done, in_progress, todo"}}` |

---

### GET /tasks/{id}

Fetch a single task. Requires at minimum `view` permission.

**Response `200`**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "Write unit tests",
  "description": "Cover all auth endpoints",
  "status": "in_progress",
  "priority": "high",
  "created_at": "2026-06-11T10:00:00+00:00",
  "updated_at": "2026-06-11T11:00:00+00:00"
}
```

**Errors**

| Status | Message |
|---|---|
| 403 | `{"error": "Access denied"}` |
| 404 | `{"error": "Task not found"}` |

---

### PUT /tasks/{id}

Update a task. All fields are optional. Requires `edit` permission.

**Request**
```json
{
  "title": "Write unit tests (updated)",
  "status": "done"
}
```

**Response `200`** — returns the full updated task object.

**Errors**

| Status | Message |
|---|---|
| 400 | `{"error": "Validation failed", "errors": {"title": "Title cannot be empty"}}` |
| 403 | `{"error": "Access denied"}` |
| 404 | `{"error": "Task not found"}` |

---

### DELETE /tasks/{id}

Delete a task. Requires `delete` permission (or ownership).

**Response `200`**
```json
{
  "message": "Task deleted"
}
```

---

## Task Sharing

### Permission Levels

| Level | Read | Edit | Delete | Share/Revoke |
|---|---|---|---|---|
| `view` | ✓ | ✗ | ✗ | ✗ |
| `edit` | ✓ | ✓ | ✗ | ✗ |
| `delete` | ✓ | ✓ | ✓ | ✓ |
| owner (implicit) | ✓ | ✓ | ✓ | ✓ |

---

### POST /tasks/{id}/share

Share a task with another user. Requires ownership or `delete` permission.

**Request**
```json
{
  "email": "bob@example.com",
  "permission_level": "edit"
}
```

**Response `200`**
```json
{
  "message": "Task shared with bob@example.com",
  "user_id": 2,
  "permission_level": "edit"
}
```

**Errors**

| Status | Message |
|---|---|
| 400 | `{"error": "email is required"}` |
| 400 | `{"error": "Invalid permission_level. Must be one of: delete, edit, view"}` |
| 403 | `{"error": "Only the owner or users with delete permission can manage access"}` |
| 403 | `{"error": "Cannot share a task with its owner"}` |
| 404 | `{"error": "No user with email bob@example.com"}` |

---

### GET /tasks/{id}/collaborators

List users who have access to a task. Requires `view` permission.

**Response `200`**
```json
{
  "collaborators": [
    {
      "user_id": 2,
      "email": "bob@example.com",
      "permission_level": "edit"
    }
  ]
}
```

---

### DELETE /tasks/{id}/share/{user_id}

Revoke a user's access. Requires ownership or `delete` permission.

**Response `200`**
```json
{
  "message": "Access revoked"
}
```

---

### PUT /tasks/{id}/permissions/{user_id}

Update a collaborator's permission level. Requires ownership or `delete` permission.

**Request**
```json
{
  "permission_level": "view"
}
```

**Response `200`**
```json
{
  "message": "Permission updated",
  "permission_level": "view"
}
```

---

## Error Reference

All errors follow this shape:

```json
{ "error": "Human-readable message" }
```

Validation errors include a field map:

```json
{
  "error": "Validation failed",
  "errors": {
    "email": "Invalid email format",
    "password": "Must contain at least one uppercase letter"
  }
}
```

| HTTP Status | Meaning |
|---|---|
| 400 | Bad request — invalid or missing input |
| 401 | Unauthenticated — missing, invalid, or expired token |
| 403 | Forbidden — authenticated but not authorised |
| 404 | Not found |
| 409 | Conflict — duplicate resource |
| 500 | Internal server error |

---

## Rate Limits

Rate limiting is not implemented in this version. For production, add nginx or an API gateway in front with per-IP and per-user limits.
