import enum


class TicketSource(enum.StrEnum):
    WEB = "web"
    QR = "qr"
    WALK_IN = "walk-in"


class TicketStatus(enum.StrEnum):
    QUEUED = "queued"
    CALLED = "called"
    SERVING = "serving"
    COMPLETED = "completed"
    CANCELED = "canceled"
