"""Fill a running API with demo departments, staff, windows, and slots."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from query_service.settings import settings

logger = logging.getLogger(__name__)


class JsonHttp(Protocol):
    """Minimal JSON HTTP client used by the seed flow."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        token: str | None = None,
    ) -> tuple[int, object]:
        """Return status code and parsed JSON (or None)."""
        ...


@dataclass(frozen=True)
class DemoService:
    name: str
    duration_time: int


@dataclass(frozen=True)
class DemoWindow:
    label: str
    service_names: tuple[str, ...]


@dataclass(frozen=True)
class DemoDepartment:
    code: str
    address: str
    open_time: str
    close_time: str
    admin_username: str
    operator_username: str
    services: tuple[DemoService, ...]
    windows: tuple[DemoWindow, ...]


DEMO_CATALOG: tuple[DemoDepartment, ...] = (
    DemoDepartment(
        code="DEMO01",
        address="Отделение Центр",
        open_time="09:00:00",
        close_time="18:00:00",
        admin_username="admin-demo01",
        operator_username="operator-demo01",
        services=(
            DemoService(name="Консультация", duration_time=10),
            DemoService(name="Оформление", duration_time=15),
        ),
        windows=(
            DemoWindow(label="Окно 1", service_names=("Консультация", "Оформление")),
            DemoWindow(label="Окно 2", service_names=("Консультация",)),
        ),
    ),
    DemoDepartment(
        code="DEMO02",
        address="Отделение Север",
        open_time="09:00:00",
        close_time="18:00:00",
        admin_username="admin-demo02",
        operator_username="operator-demo02",
        services=(
            DemoService(name="Консультация", duration_time=10),
            DemoService(name="Оформление", duration_time=15),
        ),
        windows=(
            DemoWindow(label="Окно 1", service_names=("Консультация", "Оформление")),
            DemoWindow(label="Окно 2", service_names=("Консультация",)),
        ),
    ),
)


class UrllibJsonHttp:
    """stdlib HTTP client against a running API process."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            msg = "seed API URL must be an http(s) URL with a host"
            raise ValueError(msg)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        token: str | None = None,
    ) -> tuple[int, object]:
        return await asyncio.to_thread(self._sync_request, method, path, json_body, token)

    def _sync_request(
        self,
        method: str,
        path: str,
        json_body: object | None,
        token: str | None,
    ) -> tuple[int, object]:
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        request = Request(self.base_url + path, data=data, headers=headers, method=method)  # noqa: S310
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                raw = response.read()
                status = int(response.status)
        except HTTPError as exc:
            raw = exc.read()
            status = int(exc.code)
        except URLError as exc:
            msg = f"cannot reach API at {self.base_url}: {exc.reason}"
            raise RuntimeError(msg) from exc

        if not raw:
            return status, None
        return status, json.loads(raw)


def _as_object(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        msg = f"expected JSON object, got {type(data).__name__}"
        raise RuntimeError(msg)
    return data


def _as_list(data: object) -> list[Any]:
    if not isinstance(data, list):
        msg = f"expected JSON array, got {type(data).__name__}"
        raise RuntimeError(msg)
    return data


def _require_status(status: int, data: object, allowed: set[int], path: str) -> None:
    if status in allowed:
        return
    msg = f"{path} returned {status}: {data}"
    raise RuntimeError(msg)


async def _signin(http: JsonHttp, username: str, password: str) -> str:
    status, data = await http.request(
        "POST",
        "/api/auth/signin",
        json_body={"username": username, "password": password},
    )
    _require_status(status, data, {200}, "POST /api/auth/signin")
    token = _as_object(data).get("access_token")
    if not isinstance(token, str) or not token:
        msg = "sign-in response has no access_token"
        raise RuntimeError(msg)
    return token


async def _get_departments(http: JsonHttp) -> list[dict[str, Any]]:
    status, data = await http.request("GET", "/api/departments")
    _require_status(status, data, {200}, "GET /api/departments")
    return [_as_object(item) for item in _as_list(data)]


async def _ensure_department(http: JsonHttp, token: str, spec: DemoDepartment) -> dict[str, Any]:
    for item in await _get_departments(http):
        if item.get("code") == spec.code:
            return item

    status, data = await http.request(
        "POST",
        "/api/departments",
        json_body={
            "code": spec.code,
            "address": spec.address,
            "open_time": spec.open_time,
            "close_time": spec.close_time,
            "is_active": True,
        },
        token=token,
    )
    if status == 409:
        for item in await _get_departments(http):
            if item.get("code") == spec.code:
                return item
        msg = f"department {spec.code} reported as duplicate but is missing from GET"
        raise RuntimeError(msg)
    _require_status(status, data, {201}, "POST /api/departments")
    return _as_object(data)


async def _list_staff(http: JsonHttp, token: str) -> list[dict[str, Any]]:
    status, data = await http.request("GET", "/api/staff", token=token)
    _require_status(status, data, {200}, "GET /api/staff")
    return [_as_object(item) for item in _as_list(data)]


async def _ensure_staff(
    http: JsonHttp,
    token: str,
    *,
    username: str,
    display_name: str,
    password: str,
    role: str,
    department_id: str,
) -> None:
    for item in await _list_staff(http, token):
        if item.get("username") == username:
            return

    status, data = await http.request(
        "POST",
        "/api/staff",
        json_body={
            "username": username,
            "display_name": display_name,
            "password": password,
            "role": role,
            "department_id": department_id,
        },
        token=token,
    )
    if status == 409:
        return
    _require_status(status, data, {201}, "POST /api/staff")


async def _list_services(http: JsonHttp, token: str, department_id: str) -> list[dict[str, Any]]:
    path = f"/api/departments/{department_id}/services"
    status, data = await http.request("GET", path, token=token)
    _require_status(status, data, {200}, f"GET {path}")
    return [_as_object(item) for item in _as_list(data)]


async def _ensure_service(
    http: JsonHttp,
    token: str,
    department_id: str,
    spec: DemoService,
) -> dict[str, Any]:
    for item in await _list_services(http, token, department_id):
        if item.get("name") == spec.name:
            return item

    path = f"/api/departments/{department_id}/services"
    status, data = await http.request(
        "POST",
        path,
        json_body={
            "name": spec.name,
            "duration_time": spec.duration_time,
            "is_active": True,
        },
        token=token,
    )
    _require_status(status, data, {201}, f"POST {path}")
    return _as_object(data)


async def _list_windows(http: JsonHttp, token: str, department_id: str) -> list[dict[str, Any]]:
    path = f"/api/departments/{department_id}/windows"
    status, data = await http.request("GET", path, token=token)
    _require_status(status, data, {200}, f"GET {path}")
    return [_as_object(item) for item in _as_list(data)]


async def _ensure_window(
    http: JsonHttp,
    token: str,
    department_id: str,
    spec: DemoWindow,
    service_ids_by_name: dict[str, str],
) -> None:
    for item in await _list_windows(http, token, department_id):
        if item.get("label") == spec.label:
            return

    missing = [name for name in spec.service_names if name not in service_ids_by_name]
    if missing:
        msg = f"window {spec.label} refers to unknown services: {missing}"
        raise RuntimeError(msg)

    path = f"/api/departments/{department_id}/windows"
    status, data = await http.request(
        "POST",
        path,
        json_body={
            "label": spec.label,
            "service_ids": [service_ids_by_name[name] for name in spec.service_names],
        },
        token=token,
    )
    if status == 409:
        return
    _require_status(status, data, {201}, f"POST {path}")


async def _generate_slots(
    http: JsonHttp,
    token: str,
    *,
    department_id: str,
    service_id: str,
    slot_date: date,
    duration: int,
) -> None:
    path = f"/api/departments/{department_id}/slots:generate"
    status, data = await http.request(
        "POST",
        path,
        json_body={
            "service_id": service_id,
            "slot_date": slot_date.isoformat(),
            "capacity": 1,
            "duration": duration,
        },
        token=token,
    )
    _require_status(status, data, {201}, f"POST {path}")


async def _seed_department(
    http: JsonHttp,
    token: str,
    spec: DemoDepartment,
    *,
    staff_password: str,
    slot_dates: tuple[date, date],
) -> None:
    department = await _ensure_department(http, token, spec)
    department_id = department.get("id")
    if not isinstance(department_id, str):
        msg = f"department {spec.code} has no id"
        raise RuntimeError(msg)

    await _ensure_staff(
        http,
        token,
        username=spec.admin_username,
        display_name=f"Admin {spec.code}",
        password=staff_password,
        role="admin",
        department_id=department_id,
    )
    await _ensure_staff(
        http,
        token,
        username=spec.operator_username,
        display_name=f"Operator {spec.code}",
        password=staff_password,
        role="operator",
        department_id=department_id,
    )

    service_ids_by_name: dict[str, str] = {}
    durations_by_id: dict[str, int] = {}
    for service_spec in spec.services:
        service = await _ensure_service(http, token, department_id, service_spec)
        service_id = service.get("id")
        if not isinstance(service_id, str):
            msg = f"service {service_spec.name} has no id"
            raise RuntimeError(msg)
        service_ids_by_name[service_spec.name] = service_id
        duration = service.get("duration_time", service_spec.duration_time)
        durations_by_id[service_id] = duration if isinstance(duration, int) else service_spec.duration_time

    for window_spec in spec.windows:
        await _ensure_window(http, token, department_id, window_spec, service_ids_by_name)

    for service_id, duration in durations_by_id.items():
        for slot_date in slot_dates:
            await _generate_slots(
                http,
                token,
                department_id=department_id,
                service_id=service_id,
                slot_date=slot_date,
                duration=duration,
            )

    logger.info("seeded department %s", spec.code)


async def seed_demo(
    http: JsonHttp,
    *,
    username: str,
    password: str,
    staff_password: str,
    catalog: tuple[DemoDepartment, ...] = DEMO_CATALOG,
    timezone: str | None = None,
) -> None:
    """Create demo catalog through the public HTTP API as root."""
    token = await _signin(http, username, password)
    tz = ZoneInfo(timezone or settings.queue_timezone)
    today = datetime.now(tz).date()
    slot_dates = (today, today + timedelta(days=1))
    for spec in catalog:
        await _seed_department(
            http,
            token,
            spec,
            staff_password=staff_password,
            slot_dates=slot_dates,
        )


async def _amain() -> None:
    username = settings.bootstrap_username.strip().lower()
    password = settings.bootstrap_password.strip()
    staff_password = (settings.seed_staff_password or password).strip()
    if not username or not password:
        logger.error("bootstrap username or password are not set")
        raise SystemExit(1)

    http = UrllibJsonHttp(settings.seed_api_url)
    await seed_demo(
        http,
        username=username,
        password=password,
        staff_password=staff_password,
    )
    logger.info("demo seed finished")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
