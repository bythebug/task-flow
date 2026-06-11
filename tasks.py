import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from cache import cache_user_tasks, get_cached_tasks, invalidate_user_cache
from database import timed_query
from middleware import check_task_access, handle_errors, require_auth
from models import PermissionLevel, Task, TaskPriority, TaskStatus
from validators import validate_task_fields
from permissions import (
    PermissionDeniedError,
    TaskNotFoundError,
    UserNotFoundError,
    check_permission,
    get_task_collaborators,
    revoke_access,
    share_task,
    update_permission,
)

logger = logging.getLogger(__name__)

_VALID_STATUSES = {s.value for s in TaskStatus}
_VALID_PRIORITIES = {p.value for p in TaskPriority}
_VALID_PERMISSION_LEVELS = {p.value for p in PermissionLevel}


def _task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority.value,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def create_tasks_blueprint(Session):
    tasks_bp = Blueprint("tasks", __name__)

    # ------------------------------------------------------------------ #
    # GET /tasks
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/", methods=["GET"])
    @require_auth
    @handle_errors
    def list_tasks():
        try:
            page = max(1, int(request.args.get("page", 1)))
            limit = min(100, max(1, int(request.args.get("limit", 20))))
        except ValueError:
            return jsonify({"error": "page and limit must be integers"}), 400

        status_filter = request.args.get("status")
        priority_filter = request.args.get("priority")

        if status_filter and status_filter not in _VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"}), 400
        if priority_filter and priority_filter not in _VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(_VALID_PRIORITIES))}"}), 400

        use_cache = not status_filter and not priority_filter

        if use_cache:
            all_tasks = get_cached_tasks(g.user_id)
            if all_tasks is None:
                with timed_query("list_tasks_db"):
                    all_tasks = [
                        _task_to_dict(t)
                        for t in Session.query(Task)
                        .filter(Task.user_id == g.user_id)
                        .order_by(Task.created_at.desc())
                        .all()
                    ]
                cache_user_tasks(g.user_id, all_tasks)

            total = len(all_tasks)
            tasks_page = all_tasks[(page - 1) * limit : page * limit]
            return jsonify({
                "tasks": tasks_page,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": max(1, (total + limit - 1) // limit),
            }), 200

        # Filtered path — skip cache, let the DB do the work
        with timed_query("list_tasks_filtered"):
            query = Session.query(Task).filter(Task.user_id == g.user_id)
            if status_filter:
                query = query.filter(Task.status == TaskStatus(status_filter))
            if priority_filter:
                query = query.filter(Task.priority == TaskPriority(priority_filter))

            total = query.count()
            tasks = (
                query.order_by(Task.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
                .all()
            )

        return jsonify({
            "tasks": [_task_to_dict(t) for t in tasks],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": max(1, (total + limit - 1) // limit),
        }), 200

    # ------------------------------------------------------------------ #
    # POST /tasks
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/", methods=["POST"])
    @require_auth
    @handle_errors
    def create_task():
        data = request.get_json(silent=True) or {}
        cleaned = validate_task_fields(data, require_title=True)

        task = Task(
            user_id=g.user_id,
            title=cleaned["title"],
            description=cleaned.get("description"),
            status=TaskStatus(cleaned.get("status", TaskStatus.todo.value)),
            priority=TaskPriority(cleaned.get("priority", TaskPriority.medium.value)),
        )
        Session.add(task)
        Session.commit()
        Session.refresh(task)

        invalidate_user_cache(g.user_id)
        logger.info("task created id=%s user_id=%s", task.id, g.user_id)
        return jsonify(_task_to_dict(task)), 201

    # ------------------------------------------------------------------ #
    # GET /tasks/<id>  — requires view permission
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["GET"])
    @require_auth
    @handle_errors
    def get_task(task_id: int):
        if err := check_task_access(Session, task_id, g.user_id, PermissionLevel.view):
            return err
        return jsonify(_task_to_dict(Session.get(Task, task_id))), 200

    # ------------------------------------------------------------------ #
    # PUT /tasks/<id>  — requires edit permission
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["PUT"])
    @require_auth
    @handle_errors
    def update_task(task_id: int):
        if err := check_task_access(Session, task_id, g.user_id, PermissionLevel.edit):
            return err

        task = Session.get(Task, task_id)
        data = request.get_json(silent=True) or {}
        cleaned = validate_task_fields(data, require_title=False)

        if "title" in cleaned:
            task.title = cleaned["title"]
        if "description" in cleaned:
            task.description = cleaned["description"]
        if "status" in cleaned:
            task.status = TaskStatus(cleaned["status"])
        if "priority" in cleaned:
            task.priority = TaskPriority(cleaned["priority"])

        task.updated_at = datetime.now(timezone.utc)
        Session.commit()
        Session.refresh(task)

        invalidate_user_cache(task.user_id)
        logger.info("task updated id=%s user_id=%s", task.id, g.user_id)
        return jsonify(_task_to_dict(task)), 200

    # ------------------------------------------------------------------ #
    # DELETE /tasks/<id>  — requires delete permission
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["DELETE"])
    @require_auth
    @handle_errors
    def delete_task(task_id: int):
        if err := check_task_access(Session, task_id, g.user_id, PermissionLevel.delete):
            return err

        task = Session.get(Task, task_id)
        Session.delete(task)
        Session.commit()

        invalidate_user_cache(g.user_id)
        logger.info("task deleted id=%s user_id=%s", task_id, g.user_id)
        return jsonify({"message": "Task deleted"}), 200

    # ------------------------------------------------------------------ #
    # POST /tasks/<id>/share
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>/share", methods=["POST"])
    @require_auth
    @handle_errors
    def share_task_endpoint(task_id: int):
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        permission_level = data.get("permission_level", PermissionLevel.view.value)

        if not email:
            return jsonify({"error": "email is required"}), 400
        if permission_level not in _VALID_PERMISSION_LEVELS:
            return jsonify({"error": f"Invalid permission_level. Must be one of: {', '.join(sorted(_VALID_PERMISSION_LEVELS))}"}), 400

        try:
            target = share_task(Session, task_id, g.user_id, email, permission_level)
        except TaskNotFoundError:
            return jsonify({"error": "Task not found"}), 404
        except UserNotFoundError:
            return jsonify({"error": f"No user with email {email}"}), 404
        except PermissionDeniedError as e:
            return jsonify({"error": str(e)}), 403

        logger.info("task shared task_id=%s with user_id=%s level=%s", task_id, target.id, permission_level)
        return jsonify({"message": f"Task shared with {email}", "user_id": target.id, "permission_level": permission_level}), 200

    # ------------------------------------------------------------------ #
    # GET /tasks/<id>/collaborators
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>/collaborators", methods=["GET"])
    @require_auth
    @handle_errors
    def list_collaborators(task_id: int):
        try:
            collaborators = get_task_collaborators(Session, task_id, g.user_id)
        except TaskNotFoundError:
            return jsonify({"error": "Task not found"}), 404
        except PermissionDeniedError:
            return jsonify({"error": "Access denied"}), 403

        return jsonify({"collaborators": collaborators}), 200

    # ------------------------------------------------------------------ #
    # DELETE /tasks/<id>/share/<user_id>
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>/share/<int:target_user_id>", methods=["DELETE"])
    @require_auth
    @handle_errors
    def revoke_access_endpoint(task_id: int, target_user_id: int):
        try:
            revoke_access(Session, task_id, g.user_id, target_user_id)
        except TaskNotFoundError:
            return jsonify({"error": "Task not found"}), 404
        except PermissionDeniedError as e:
            return jsonify({"error": str(e)}), 403

        logger.info("access revoked task_id=%s target_user_id=%s by user_id=%s", task_id, target_user_id, g.user_id)
        return jsonify({"message": "Access revoked"}), 200

    # ------------------------------------------------------------------ #
    # PUT /tasks/<id>/permissions/<user_id>
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>/permissions/<int:target_user_id>", methods=["PUT"])
    @require_auth
    @handle_errors
    def update_permission_endpoint(task_id: int, target_user_id: int):
        data = request.get_json(silent=True) or {}
        permission_level = data.get("permission_level", "")

        if permission_level not in _VALID_PERMISSION_LEVELS:
            return jsonify({"error": f"Invalid permission_level. Must be one of: {', '.join(sorted(_VALID_PERMISSION_LEVELS))}"}), 400

        try:
            update_permission(Session, task_id, g.user_id, target_user_id, permission_level)
        except TaskNotFoundError:
            return jsonify({"error": "Task not found"}), 404
        except PermissionDeniedError as e:
            return jsonify({"error": str(e)}), 403

        logger.info("permission updated task_id=%s target_user_id=%s level=%s", task_id, target_user_id, permission_level)
        return jsonify({"message": "Permission updated", "permission_level": permission_level}), 200

    return tasks_bp
