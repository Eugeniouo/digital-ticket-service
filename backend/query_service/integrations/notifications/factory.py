from query_service.integrations.notifications.demo import DemoNotificationAdapter
from query_service.integrations.notifications.port import NotificationGateway
from query_service.settings import Settings

DEMO_ADAPTER_NAME = "demo"


def create_notification_adapter(settings: Settings) -> NotificationGateway:
    kind = settings.notify_adapter

    if kind == DEMO_ADAPTER_NAME:
        return DemoNotificationAdapter(force_failure=settings.notify_force_failure)

    raise ValueError(f"unknown notification adapter: {kind}, available: {DEMO_ADAPTER_NAME}")
