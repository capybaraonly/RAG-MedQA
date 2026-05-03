from functools import wraps

from quart import jsonify

from api.apps import current_user


def admin_required(f):
    """Decorator that restricts a route to superusers only."""
    import asyncio

    @wraps(f)
    async def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superuser:
            return jsonify({"retcode": 109, "retmsg": "Admin permission required.", "data": False}), 403
        result = f(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return decorated
