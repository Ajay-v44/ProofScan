from uuid import UUID

from sqlalchemy import ColumnElement, select, tuple_
from sqlalchemy.orm import aliased

from .db import Notification, Verification
from .handoff_models import Handoff

PAGE_SIZE = 30


def before_record(
    model: type[Verification] | type[Notification] | type[Handoff], owner: UUID, cursor: UUID
) -> ColumnElement[bool]:
    anchor = aliased(model)
    position = (
        select(anchor.created_at, anchor.id)
        .where(anchor.owner_id == owner, anchor.id == cursor)
        .scalar_subquery()
    )
    return tuple_(model.created_at, model.id) < position
