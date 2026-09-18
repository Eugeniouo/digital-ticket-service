"""Database classes for accessing database tables."""

from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.slot import Slot
from query_service.database.models.ticket import Ticket
from query_service.database.models.window import Window, WindowService

__all__ = [
    "Department",
    "Service",
    "Slot",
    "Ticket",
    "Window",
    "WindowService",
]
