from urllib.parse import urlparse
from uuid import UUID

import segno

from query_service.modules.departments.exceptions import InvalidQrBaseUrlError

VISITOR_PATH = "/src/visitor.html"


def department_qr_payload(base_url: str, department_id: UUID) -> str:
    parsed = urlparse(base_url.strip())
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not host
        or host == "localhost"
        or host.endswith(".localhost")
        or host == "127.0.0.1"
        or host.startswith("127.")
        or host.startswith("0.")
        or host in {"::1", "[::1]"}
    ):
        raise InvalidQrBaseUrlError

    origin = f"https://{parsed.netloc}"
    return f"{origin}{VISITOR_PATH}?department={department_id}"


def render_qr_svg(payload: str) -> str:
    qr = segno.make_qr(payload, error="M")
    return qr.svg_inline(scale=7, border=4)
