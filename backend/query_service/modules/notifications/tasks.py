"""Celery tasks for notification outbox drain."""

import asyncio

from query_service.celery_app import celery_app
from query_service.modules.notifications.worker import drain


# Do not add Celery autoretry
@celery_app.task(name="notifications.drain_outbox")
def drain_notification_outbox() -> None:
    asyncio.run(drain())
