from datetime import time
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from query_service.database.models.department import Department
from sqlalchemy.ext.asyncio import AsyncSession


async def test_empty_departments(client: AsyncClient) -> None:
    response = await client.get("/api/departments")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_and_detail(client: AsyncClient, dbsession: AsyncSession) -> None:
    departments = [
        Department(
            id=UUID(int=index),
            code=f"{index:06d}",
            address=f"Street {index}",
            open_time=time(9),
            close_time=time(18),
            is_active=active,
        )
        for index, active in [(2, False), (3, True), (1, True)]
    ]
    dbsession.add_all(departments)
    await dbsession.flush()
    dbsession.expunge_all()

    response = await client.get("/api/departments")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(UUID(int=index)),
            "code": f"{index:06d}",
            "address": f"Street {index}",
            "open_time": "09:00:00",
            "close_time": "18:00:00",
            "is_active": active,
        }
        for index, active in [(1, True), (2, False), (3, True)]
    ]
    for item in response.json():
        detail = await client.get(f"/api/departments/{item['id']}")
        assert detail.status_code == 200
        assert detail.json() == item


async def test_department_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/departments/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Department not found"}


@pytest.mark.parametrize("department_id", ["not-a-uuid", "123", "' OR 1=1 --", "x" * 1000])
async def test_invalid_department_id(client: AsyncClient, department_id: str) -> None:
    response = await client.get(f"/api/departments/{department_id}")
    assert response.status_code == 422


async def test_department_defaults(client: AsyncClient, dbsession: AsyncSession) -> None:
    department = Department(
        code="369000",
        address="ул. Мира, 1",
        open_time=time(22),
        close_time=time(6),
    )
    dbsession.add(department)
    await dbsession.flush()
    department_id = department.id
    assert isinstance(department_id, UUID)
    assert department_id.version == 4
    dbsession.expunge_all()

    response = await client.get(f"/api/departments/{department_id}")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(department_id),
        "code": "369000",
        "address": "ул. Мира, 1",
        "open_time": "22:00:00",
        "close_time": "06:00:00",
        "is_active": True,
    }


@pytest.mark.skip(reason="staff auth not covered by tests yet")
async def test_create_department(client: AsyncClient) -> None:
    response = await client.post(
        "/api/departments",
        json={
            "code": "369001",
            "address": "ул. Ленина, 10",
            "open_time": "09:00:00",
            "close_time": "18:00:00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "369001"
    assert body["address"] == "ул. Ленина, 10"
    assert body["open_time"] == "09:00:00"
    assert body["close_time"] == "18:00:00"
    assert body["is_active"] is True
    assert UUID(body["id"]).version == 4

    detail = await client.get(f"/api/departments/{body['id']}")
    assert detail.status_code == 200
    assert detail.json() == body


@pytest.mark.skip(reason="staff auth not covered by tests yet")
async def test_create_department_inactive(client: AsyncClient) -> None:
    response = await client.post(
        "/api/departments",
        json={
            "code": "369002",
            "address": "ул. Ночная, 1",
            "open_time": "22:00:00",
            "close_time": "06:00:00",
            "is_active": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is False


# Не тестируем "отсутствие" методов ошибкой 405. По сути, мы можем их поддерживать, если это необходимо.
