from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from query_service.database.models.notification_outbox import NotificationOutbox, NotificationOutboxStatus
from query_service.integrations.notifications.exceptions import NotificationDeliveryError
from query_service.integrations.notifications.port import NotificationEvent, NotificationMessage
from query_service.modules.notifications.worker import deliver_row


def _pending_row() -> NotificationOutbox:
    message = NotificationMessage(
        id=uuid4(),
        event_type=NotificationEvent.TICKET_CALLED,
        ticket_id=uuid4(),
        ticket_label="A1",
        department_id=uuid4(),
        window_label="1",
    )

    return NotificationOutbox(
        id=message.id,
        idempotency_key=f"{message.ticket_id}:{message.event_type}",
        event_type=message.event_type,
        ticket_id=message.ticket_id,
        payload=message.model_dump(mode="json"),
        status=NotificationOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_deliver_row_marks_sent_on_success() -> None:
    row = _pending_row()

    async def send(_message: NotificationMessage) -> None:
        return

    await deliver_row(row, SimpleNamespace(send=send), timeout_seconds=1.0, max_attempts=5)

    assert row.status == NotificationOutboxStatus.SENT
    assert row.sent_at is not None
    assert row.last_error is None


@pytest.mark.asyncio
async def test_deliver_row_retries_then_fails() -> None:
    row = _pending_row()

    async def send(_message: NotificationMessage) -> None:
        raise NotificationDeliveryError("unavailable")

    adapter = SimpleNamespace(send=send)

    await deliver_row(row, adapter, timeout_seconds=1.0, max_attempts=2)

    assert row.status == NotificationOutboxStatus.PENDING
    assert row.attempts == 1
    assert row.last_error == "unavailable"
    assert row.next_attempt_at > datetime.now(UTC)

    await deliver_row(row, adapter, timeout_seconds=1.0, max_attempts=2)

    assert cast(NotificationOutboxStatus, row.status) == NotificationOutboxStatus.FAILED
    assert row.attempts == 2
    assert row.sent_at is None


@pytest.mark.asyncio
async def test_deliver_row_marks_timeout() -> None:
    row = _pending_row()

    async def send(_message: NotificationMessage) -> None:
        await asyncio.sleep(1)

    await deliver_row(row, SimpleNamespace(send=send), timeout_seconds=0.01, max_attempts=5)

    assert row.status == NotificationOutboxStatus.PENDING
    assert row.attempts == 1
    assert row.last_error == "timeout"
    assert row.next_attempt_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_deliver_row_marks_invalid_payload_failed() -> None:
    row = _pending_row()
    row.payload = {"ticket_label": "A1"}
    send_called = False

    async def send(_message: NotificationMessage) -> None:
        nonlocal send_called
        send_called = True

    await deliver_row(row, SimpleNamespace(send=send), timeout_seconds=1.0, max_attempts=5)

    assert send_called is False
    assert row.status == NotificationOutboxStatus.FAILED
    assert row.attempts == 1
    assert row.sent_at is None
    assert row.last_error is not None
