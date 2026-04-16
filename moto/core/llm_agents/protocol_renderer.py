from __future__ import annotations

from typing import Any

from moto.core.serialize import (
    EC2Serializer,
    JSONSerializer,
    QuerySerializer,
    RestJSONSerializer,
    RestXMLSerializer,
)
from moto.core.utils import get_service_model

from .normalizer import CanonicalRequest


def render_protocol_response(
    canonical: CanonicalRequest,
    payload: dict[str, Any],
    render_meta: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    service_model = get_service_model(canonical.service)
    operation_model = service_model.operation_model(canonical.operation)
    serializer = _serializer_for_protocol(service_model.metadata.get("protocol", "json"))(
        operation_model
    )
    response = serializer.serialize(payload)
    meta = dict(render_meta)
    meta["status_code"] = response["status_code"]
    meta["headers"] = dict(response["headers"])
    return response["body"], meta


def _serializer_for_protocol(protocol: str) -> Any:
    if protocol == "query":
        return QuerySerializer
    if protocol == "ec2":
        return EC2Serializer
    if protocol == "rest-xml":
        return RestXMLSerializer
    if protocol == "rest-json":
        return RestJSONSerializer
    return JSONSerializer
