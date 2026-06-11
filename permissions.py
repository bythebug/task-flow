from error_handlers import AppError
from models import PermissionLevel, Task, TaskPermission, User

_LEVEL_RANK = {
    PermissionLevel.view: 1,
    PermissionLevel.edit: 2,
    PermissionLevel.delete: 3,
}


class PermissionDeniedError(AppError):
    pass


class UserNotFoundError(AppError):
    pass


class TaskNotFoundError(AppError):
    pass


def check_permission(session, task_id: int, user_id: int, required_level: PermissionLevel) -> bool:
    """Return True if user has at least required_level on the task. Owner always passes."""
    task = session.get(Task, task_id)
    if task is None:
        return False
    if task.user_id == user_id:
        return True
    perm = session.query(TaskPermission).filter_by(task_id=task_id, user_id=user_id).first()
    if perm is None:
        return False
    return _LEVEL_RANK[perm.permission_level] >= _LEVEL_RANK[required_level]


def _assert_can_manage(session, task: Task, requester_id: int) -> None:
    """Raise PermissionDeniedError unless requester is the owner or has delete-level access."""
    if task.user_id == requester_id:
        return
    perm = session.query(TaskPermission).filter_by(task_id=task.id, user_id=requester_id).first()
    if not perm or _LEVEL_RANK[perm.permission_level] < _LEVEL_RANK[PermissionLevel.delete]:
        raise PermissionDeniedError("Only the owner or users with delete permission can manage access")


def share_task(session, task_id: int, requester_id: int, target_email: str, permission_level: str) -> User:
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    _assert_can_manage(session, task, requester_id)

    target = session.query(User).filter_by(email=target_email).first()
    if target is None:
        raise UserNotFoundError(f"No user with email {target_email}")
    if target.id == task.user_id:
        raise PermissionDeniedError("Cannot share a task with its owner")

    level = PermissionLevel(permission_level)
    existing = session.query(TaskPermission).filter_by(task_id=task_id, user_id=target.id).first()
    if existing:
        existing.permission_level = level
    else:
        session.add(TaskPermission(task_id=task_id, user_id=target.id, permission_level=level))

    session.commit()
    return target


def revoke_access(session, task_id: int, requester_id: int, target_user_id: int) -> None:
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    _assert_can_manage(session, task, requester_id)

    perm = session.query(TaskPermission).filter_by(task_id=task_id, user_id=target_user_id).first()
    if perm is None:
        raise PermissionDeniedError("User does not have access to this task")

    session.delete(perm)
    session.commit()


def update_permission(session, task_id: int, requester_id: int, target_user_id: int, new_level: str) -> TaskPermission:
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    _assert_can_manage(session, task, requester_id)

    perm = session.query(TaskPermission).filter_by(task_id=task_id, user_id=target_user_id).first()
    if perm is None:
        raise PermissionDeniedError("User does not have access to this task")

    perm.permission_level = PermissionLevel(new_level)
    session.commit()
    return perm


def get_task_collaborators(session, task_id: int, requester_id: int) -> list[dict]:
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    if not check_permission(session, task_id, requester_id, PermissionLevel.view):
        raise PermissionDeniedError("Access denied")

    result = []
    for perm in session.query(TaskPermission).filter_by(task_id=task_id).all():
        user = session.get(User, perm.user_id)
        result.append({
            "user_id": user.id,
            "email": user.email,
            "permission_level": perm.permission_level.value,
        })
    return result
