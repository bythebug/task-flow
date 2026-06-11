-- task-flow database schema

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_email ON users (email);


CREATE TYPE task_status   AS ENUM ('todo', 'in_progress', 'done', 'cancelled');
CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high', 'urgent');

CREATE TABLE tasks (
    id          SERIAL        PRIMARY KEY,
    user_id     INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255)  NOT NULL,
    description TEXT,
    status      task_status   NOT NULL DEFAULT 'todo',
    priority    task_priority NOT NULL DEFAULT 'medium',
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_tasks_user_id    ON tasks (user_id);
CREATE INDEX ix_tasks_status     ON tasks (status);
CREATE INDEX ix_tasks_user_status ON tasks (user_id, status);


CREATE TYPE permission_level AS ENUM ('view', 'edit', 'delete');

CREATE TABLE task_permissions (
    id               SERIAL           PRIMARY KEY,
    task_id          INTEGER          NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id          INTEGER          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_level permission_level NOT NULL DEFAULT 'view',
    UNIQUE (task_id, user_id)
);

CREATE INDEX ix_task_permissions_task_id ON task_permissions (task_id);
CREATE INDEX ix_task_permissions_user_id ON task_permissions (user_id);
