import logging

from query_service.integrations.notifications.exceptions import NotificationDeliveryError
from query_service.integrations.notifications.port import NotificationMessage

logger = logging.getLogger(__name__)


class DemoNotificationAdapter:
    """Adapter pattern."""

    def __init__(self, force_failure: bool = False) -> None:
        self._force_failure = force_failure

    async def send(self, message: NotificationMessage) -> None:
        # By setting this parameter to `True`, we can observe, how our notifications service should behave in case of failures.
        if self._force_failure:
            raise NotificationDeliveryError("demo notifications service is unavailable")

        logger.info("notification.delivered %s", message.model_dump(mode="json"))
