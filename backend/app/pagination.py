import base64
import json
from datetime import date, datetime
from typing import TypeVar

from sqlalchemy import asc, desc
from sqlalchemy.orm import Query, Session

T = TypeVar("T")


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def cursor_encode(cursor: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(cursor, default=_json_default).encode()).decode().rstrip("=")


def cursor_decode(cursor: str) -> dict:
    padded = cursor + "=" * (-len(cursor) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode())


def paginate(
    db: Session,
    query: Query,
    *,
    cursor: str | None,
    limit: int,
    sort_column,
    sort_asc: bool = False,
) -> tuple[list[T], str | None, bool]:
    column = sort_column
    if sort_asc:
        query = query.order_by(asc(column))
    else:
        query = query.order_by(desc(column))

    if cursor:
        decoded = cursor_decode(cursor)
        value = decoded.get("value")
        if value is not None:
            # Rehydrate ISO strings back to datetime so the comparison binds
            # against the column's real type (encode side serializes via isoformat).
            if isinstance(value, str) and sort_column.type.python_type in (datetime, date):
                value = datetime.fromisoformat(value)
            if sort_asc:
                query = query.filter(column > value)
            else:
                query = query.filter(column < value)

    items = query.limit(limit + 1).all()
    has_more = len(items) > limit
    items = items[:limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = cursor_encode({"value": getattr(last, sort_column.key)})

    return items, next_cursor, has_more
