from uuid import UUID

import segno
from yarl import URL

from query_service.modules.departments.exceptions import InvalidQrBaseUrlError
from query_service.settings import settings


def department_qr_payload(department_id: UUID) -> str:
    origin = URL(settings.frontend_origin)
    if origin.scheme not in {"http", "https"} or not origin.host:
        raise InvalidQrBaseUrlError

    path = settings.visitor_path if settings.visitor_path.startswith("/") else f"/{settings.visitor_path}"
    return str(origin.with_path(path).with_query({"department": str(department_id)}))


def render_qr_svg(payload: str) -> str:
    qr = segno.make_qr(payload, error="M")
    return qr.svg_inline(scale=7, border=4)
