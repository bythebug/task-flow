import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from middleware import handle_errors, require_auth
from models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

_VALID_STATUSES = {s.value for s in TaskStatus}
_VALID_PRIORITIES = {p.value for p in TaskPriority}


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


def _get_owned_task(Session, task_id: int, user_id: int):
    """Return (task, error_response) — one of the two is always None."""
    task = Session.get(Task, task_id)
    if task is None:
        return None, (jsonify({"error": "Task not found"}), 404)
    if task.user_id != user_id:
        return None, (jsonify({"error": "Access denied"}), 403)
    return task, None


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
        title = (data.get("title") or "").strip()

        if not title:
            return jsonify({"error": "title is required"}), 400

        status_val = data.get("status", TaskStatus.todo.value)
        priority_val = data.get("priority", TaskPriority.medium.value)

        if status_val not in _VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"}), 400
        if priority_val not in _VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(_VALID_PRIORITIES))}"}), 400

        task = Task(
            user_id=g.user_id,
            title=title,
            description=(data.get("description") or "").strip() or None,
            status=TaskStatus(status_val),
            priority=TaskPriority(priority_val),
        )
        Session.add(task)
        Session.commit()
        Session.refresh(task)

        logger.info("task created id=%s user_id=%s", task.id, g.user_id)
        return jsonify(_task_to_dict(task)), 201

    # ------------------------------------------------------------------ #
    # GET /tasks/<id>
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["GET"])
    @require_auth
    @handle_errors
    def get_task(task_id: int):
        task, err = _get_owned_task(Session, task_id, g.user_id)
        if err:
            return err
        return jsonify(_task_to_dict(task)), 200

    # ------------------------------------------------------------------ #
    # PUT /tasks/<id>
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["PUT"])
    @require_auth
    @handle_errors
    def update_task(task_id: int):
        task, err = _get_owned_task(Session, task_id, g.user_id)
        if err:
            return err

        data = request.get_json(silent=True) or {}

        if "title" in data:
            title = (data["title"] or "").strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            task.title = title

        if "description" in data:
            task.description = (data["description"] or "").strip() or None

        if "status" in data:
            if data["status"] not in _VALID_STATUSES:
                return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"}), 400
            task.status = TaskStatus(data["status"])

        if "priority" in data:
            if data["priority"] not in _VALID_PRIORITIES:
                return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(_VALID_PRIORITIES))}"}), 400
            task.priority = TaskPriority(data["priority"])

        task.updated_at = datetime.now(timezone.utc)
        Session.commit()
        Session.refresh(task)

        logger.info("task updated id=%s user_id=%s", task.id, g.user_id)
        return jsonify(_task_to_dict(task)), 200

    # ------------------------------------------------------------------ #
    # DELETE /tasks/<id>
    # ------------------------------------------------------------------ #
    @tasks_bp.route("/<int:task_id>", methods=["DELETE"])
    @require_auth
    @handle_errors
    def delete_task(task_id: int):
        task, err = _get_owned_task(Session, task_id, g.user_id)
        if err:
            return err

        Session.delete(task)
        Session.commit()

        logger.info("task deleted id=%s user_id=%s", task_id, g.user_id)
        return jsonify({"message": "Task deleted"}), 200

    return tasks_bp
