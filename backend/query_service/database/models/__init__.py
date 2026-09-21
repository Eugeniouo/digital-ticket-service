"""Database classes for accessing database tables."""

from query_service.database.models.department import Department
from query_service.database.models.issue import Issue
from query_service.database.models.notification_outbox import NotificationOutbox
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.staff import Staff, StaffRole
from query_service.database.models.ticket import Ticket
from query_service.database.models.ticket_labels import TicketCounter
from query_service.database.models.ticket_status_history import TicketStatusHistory
from query_service.database.models.window import Window, WindowService

__all__ = [
    "Department",
    "Issue",
    "NotificationOutbox",
    "Service",
    "Slot",
    "Staff",
    "StaffRole",
    "Ticket",
    "TicketCounter",
    "TicketStatusHistory",
    "Window",
    "WindowService",
]
