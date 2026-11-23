from enum import StrEnum


class Status(StrEnum):
    DRAFT = "DRAFT"
    LINK_CREATED = "LINK_CREATED"
    SELLER_OPENED = "SELLER_OPENED"
    CONSENTED = "CONSENTED"
    SCANNING = "SCANNING"
    REPORT_READY = "REPORT_READY"
    SELLER_REVIEW = "SELLER_REVIEW"
    SHARED = "SHARED"
    DECLINED = "DECLINED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TRANSITIONS = {
    Status.DRAFT: {Status.LINK_CREATED, Status.CANCELLED},
    Status.LINK_CREATED: {Status.SELLER_OPENED, Status.EXPIRED, Status.CANCELLED},
    Status.SELLER_OPENED: {Status.CONSENTED, Status.EXPIRED, Status.CANCELLED},
    Status.CONSENTED: {Status.SCANNING, Status.EXPIRED, Status.CANCELLED},
    Status.SCANNING: {Status.REPORT_READY, Status.EXPIRED, Status.CANCELLED, Status.FAILED},
    Status.REPORT_READY: {Status.SELLER_REVIEW, Status.EXPIRED, Status.CANCELLED},
    Status.SELLER_REVIEW: {Status.SHARED, Status.DECLINED, Status.EXPIRED, Status.CANCELLED},
    Status.SHARED: {Status.COMPLETED},
}


class InvalidTransition(ValueError):
    pass


def transition(current: str, target: Status) -> str:
    if target not in TRANSITIONS.get(Status(current), set()):
        raise InvalidTransition(f"Cannot move from {current} to {target}.")
    return target.value
