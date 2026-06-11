import re

from app.core.error_handlers import ValidationError

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_input(value: str) -> str:
    if not value:
        return value
    return _CONTROL_CHARS_RE.sub("", value).strip()


def validate_email(email: str | None) -> str:
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError({"email": "Email is required"})
    if not _EMAIL_RE.match(email):
        raise ValidationError({"email": "Invalid email format"})
    return email


def validate_password(password: str | None) -> str:
    password = password or ""
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Must be at least 8 characters")
    else:
        if not re.search(r"[A-Z]", password):
            errors.append("Must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("Must contain at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            errors.append("Must contain at least one digit")

    if errors:
        raise ValidationError({"password": errors[0]})

    return password


def validate_task_fields(data: dict, *, require_title: bool = True) -> dict:
    from app.models import TaskPriority, TaskStatus

    errors: dict[str, str] = {}
    cleaned: dict = {}

    if "title" in data or require_title:
        title = sanitize_input(data.get("title") or "")
        if not title:
            errors["title"] = "Title is required" if require_title else "Title cannot be empty"
        elif len(title) > 255:
            errors["title"] = "Title must be 255 characters or fewer"
        else:
            cleaned["title"] = title

    if "description" in data:
        desc = sanitize_input(data.get("description") or "")
        if len(desc) > 5000:
            errors["description"] = "Description must be 5000 characters or fewer"
        else:
            cleaned["description"] = desc or None

    valid_statuses = {s.value for s in TaskStatus}
    if "status" in data:
        if data["status"] not in valid_statuses:
            errors["status"] = f"Must be one of: {', '.join(sorted(valid_statuses))}"
        else:
            cleaned["status"] = data["status"]

    valid_priorities = {p.value for p in TaskPriority}
    if "priority" in data:
        if data["priority"] not in valid_priorities:
            errors["priority"] = f"Must be one of: {', '.join(sorted(valid_priorities))}"
        else:
            cleaned["priority"] = data["priority"]

    if errors:
        raise ValidationError(errors)

    return cleaned
