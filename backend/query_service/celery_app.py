"""Celery application for notification outbox drain."""

from celery import Celery

from query_service.settings import settings

celery_app = Celery(
    "query_service",
    broker=settings.celery_broker_url,
    include=["query_service.modules.notifications.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_backend=None,  # Delivery state lives in notification outbox
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "drain-notification-outbox": {
            "task": "notifications.drain_outbox",
            "schedule": settings.notify_poll_interval_seconds,
        },
    },
)
