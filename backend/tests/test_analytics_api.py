from datetime import date, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from query_service.database.models.department import Department
from query_service.database.models.service import Service
from query_service.database.models.staff import Staff, StaffRole
from query_service.database.models.ticket import Ticket, TicketSource, TicketStatus
from query_service.database.models.ticket_status_history import TicketStatusChangeReason, TicketStatusHistory
from query_service.database.models.window import Window, WindowStatus
from query_service.modules.auth.dependencies import get_current_staff
from query_service.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession

MOSCOW = ZoneInfo("Europe/Moscow")
DAY = date(2026, 9, 20)


def _install_staff(app: FastAPI, member: Staff) -> None:
    def current() -> Staff:
        return member

    app.dependency_overrides[get_current_staff] = current


def _staff(role: StaffRole, department_id: UUID | None) -> Staff:
    return Staff(
        username=f"user-{uuid4()}",
        password_hash="hash",
        role=role,
        department_id=department_id,
        is_active=True,
    )


async def _department(session: AsyncSession) -> Department:
    department = Department(
        name=f"Analytics {uuid4()}",
        address="Street",
        open_time=time(9),
        close_time=time(18),
        is_active=True,
    )
    session.add(department)
    await session.flush()
    return department


async def test_analytics_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"/api/departments/{uuid4()}/analytics")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_operator_is_forbidden(client: AsyncClient, fastapi_app: FastAPI) -> None:
    department_id = uuid4()
    _install_staff(fastapi_app, _staff(StaffRole.OPERATOR, department_id))

    response = await client.get(f"/api/departments/{department_id}/analytics")

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


async def test_admin_of_another_department_is_forbidden(
    client: AsyncClient,
    fastapi_app: FastAPI,
    dbsession: AsyncSession,
) -> None:
    department = await _department(dbsession)
    _install_staff(fastapi_app, _staff(StaffRole.ADMIN, uuid4()))

    response = await client.get(f"/api/departments/{department.id}/analytics?date={DAY.isoformat()}")

    assert response.status_code == 403


async def test_root_gets_404_for_a_missing_department(client: AsyncClient, fastapi_app: FastAPI) -> None:
    _install_staff(fastapi_app, _staff(StaffRole.ROOT, None))

    response = await client.get(f"/api/departments/{uuid4()}/analytics?date={DAY.isoformat()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Department not found"}


@pytest.mark.parametrize("department_id", ["not-a-uuid", "123"])
async def test_invalid_department_id(client: AsyncClient, department_id: str) -> None:
    response = await client.get(f"/api/departments/{department_id}/analytics")

    assert response.status_code == 422


async def test_invalid_date_is_rejected(client: AsyncClient, fastapi_app: FastAPI, dbsession: AsyncSession) -> None:
    department = await _department(dbsession)
    _install_staff(fastapi_app, _staff(StaffRole.ADMIN, department.id))

    response = await client.get(f"/api/departments/{department.id}/analytics?date=2026-13-40")

    assert response.status_code == 422


async def test_omitted_date_is_today_in_the_department_timezone(
    client: AsyncClient,
    fastapi_app: FastAPI,
    dbsession: AsyncSession,
) -> None:
    department = await _department(dbsession)
    _install_staff(fastapi_app, _staff(StaffRole.ADMIN, department.id))

    response = await client.get(f"/api/departments/{department.id}/analytics")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == datetime.now(ZoneInfo(settings.queue_timezone)).date().isoformat()
    assert body["timezone"] == settings.queue_timezone
    assert body["served_count"] == 0
    assert [item["hour"] for item in body["hourly"]] == list(range(24))
    assert sum(item["served_count"] for item in body["hourly"]) == 0
    assert body["sources"] == [
        {"source": "appointment", "count": 0},
        {"source": "qr", "count": 0},
        {"source": "walk-in", "count": 0},
    ]
    assert body["avg_wait_seconds"] is None


async def test_admin_receives_the_full_day_chart(client: AsyncClient, fastapi_app: FastAPI, dbsession: AsyncSession) -> None:
    department = await _department(dbsession)
    service = Service(department_id=department.id, name=f"Service {uuid4()}", duration_time=10, is_active=True)
    dbsession.add(service)
    await dbsession.flush()
    first = Window(department_id=department.id, label="1", status=WindowStatus.CLOSED)
    second = Window(department_id=department.id, label="2", status=WindowStatus.CLOSED)
    dbsession.add_all([first, second])
    await dbsession.flush()

    created_at = datetime(2026, 9, 20, 10, 0, tzinfo=MOSCOW)
    called_at = datetime(2026, 9, 20, 10, 4, tzinfo=MOSCOW)
    started_at = datetime(2026, 9, 20, 10, 5, tzinfo=MOSCOW)
    completed_at = datetime(2026, 9, 20, 10, 15, tzinfo=MOSCOW)
    ticket = Ticket(
        department_id=department.id,
        service_id=service.id,
        window_id=first.id,
        source=TicketSource.WALK_IN,
        status=TicketStatus.COMPLETED,
        priority_key=1,
        ticket_label="A-001",
        created_at=created_at,
        called_at=called_at,
        started_at=started_at,
        completed_at=completed_at,
    )
    dbsession.add(ticket)
    await dbsession.flush()
    dbsession.add_all(
        [
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=None,
                new_status=TicketStatus.QUEUED,
                reason=TicketStatusChangeReason.ISSUED,
                changed_at=created_at,
            ),
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=TicketStatus.QUEUED,
                new_status=TicketStatus.CALLED,
                reason=TicketStatusChangeReason.CALLED,
                window_id=first.id,
                changed_at=called_at,
            ),
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=TicketStatus.CALLED,
                new_status=TicketStatus.SERVING,
                reason=TicketStatusChangeReason.STARTED,
                window_id=first.id,
                changed_at=started_at,
            ),
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=TicketStatus.SERVING,
                new_status=TicketStatus.COMPLETED,
                reason=TicketStatusChangeReason.COMPLETED,
                window_id=first.id,
                changed_at=completed_at,
            ),
        ],
    )
    await dbsession.flush()
    _install_staff(fastapi_app, _staff(StaffRole.ADMIN, department.id))

    response = await client.get(f"/api/departments/{department.id}/analytics?date={DAY.isoformat()}")

    assert response.status_code == 200
    body = response.json()
    assert body["department_id"] == str(department.id)
    assert body["date"] == "2026-09-20"
    assert body["timezone"] == settings.queue_timezone
    assert body["served_count"] == 1
    assert body["avg_wait_seconds"] == 300
    assert body["max_wait_seconds"] == 300
    assert body["avg_service_seconds"] == 600
    assert [item["hour"] for item in body["hourly"]] == list(range(24))
    assert sum(item["served_count"] for item in body["hourly"]) == 1
    assert body["hourly"][10]["served_count"] == 1
    assert body["hourly"][7]["served_count"] == 0
    assert body["sources"] == [
        {"source": "appointment", "count": 0},
        {"source": "qr", "count": 0},
        {"source": "walk-in", "count": 1},
    ]
    assert body["windows"] == [
        {
            "window_id": str(first.id),
            "label": "1",
            "served_seconds": 600,
            "schedule_open_seconds": 9 * 3600,
            "load_ratio": 0.0185,
        },
        {
            "window_id": str(second.id),
            "label": "2",
            "served_seconds": 0,
            "schedule_open_seconds": 9 * 3600,
            "load_ratio": 0,
        },
    ]
