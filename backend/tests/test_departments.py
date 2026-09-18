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
        Department(id=UUID(int=index), name=name, address=f"Street {index}", open_time=time(9), close_time=time(18), is_active=active)
        for index, name, active in [(2, "B Office", False), (3, "A Office", True), (1, "B Office", True)]
    ]
    dbsession.add_all(departments)
    await dbsession.flush()
    dbsession.expunge_all()

    response = await client.get("/api/departments")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(UUID(int=index)),
            "name": name,
            "address": f"Street {index}",
            "open_time": "09:00:00",
            "close_time": "18:00:00",
            "is_active": active,
        }
        for index, name, active in [(3, "A Office", True), (1, "B Office", True), (2, "B Office", False)]
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
    department = Department(name="Почта № 1", address="ул. Мира, 1", open_time=time(22), close_time=time(6))
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
        "name": "Почта № 1",
        "address": "ул. Мира, 1",
        "open_time": "22:00:00",
        "close_time": "06:00:00",
        "is_active": True,
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/departments"),
        ("PUT", "/api/departments"),
        ("PATCH", f"/api/departments/{UUID(int=1)}"),
        ("DELETE", f"/api/departments/{UUID(int=1)}"),
    ],
)
async def test_departments_are_read_only(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(method, path, json={"name": "Changed"})
    assert response.status_code == 405
