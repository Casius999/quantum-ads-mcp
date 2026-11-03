"""Offline validation of a Google API call against the API's Discovery document.

Every discovery-based Google API (GA4 Admin, Tag Manager, Merchant, YouTube, DV360, CM360,
Business Profile, Search Console, Sheets/Drive/Slides, BigQuery...) publishes a machine-readable
contract. A call is checked against it before anything leaves the process: the method exists,
required parameters are present, path parameters match their pattern, enum values are legal,
and every body field exists in the request schema with the right JSON type. Pure: the document
is passed in as a dict, so this module needs no SDK and no network.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

WRITE_HTTP = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# POST methods that only read (reporting / search); everything else that is not GET is a write.
READ_POST_NAMES = frozenset(
    {
        "search",
        "searchStream",
        "runReport",
        "runPivotReport",
        "batchRunReports",
        "batchRunPivotReports",
        "runRealtimeReport",
        "runFunnelReport",
        "checkCompatibility",
        "batchGet",
        "lookup",
        "query",
        "inspect",
        "translateText",
        "batchTranslateText",
        "translateDocument",
        "detectLanguage",
        "romanizeText",
    }
)
# Analysis verbs (Natural Language...) POST a document and return an analysis; nothing is stored.
READ_POST_PREFIXES = ("analyze", "annotate", "classify", "moderate")
_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int, str),  # int64 travels as a string in JSON
    "number": (int, float, str),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class InvalidCall(ValueError):
    """The call does not match the API's published contract."""


@dataclass(frozen=True)
class Method:
    id: str
    http_method: str
    path: str
    parameters: dict[str, dict[str, Any]]
    request_ref: str | None
    description: str
    scopes: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.id.rsplit(".", 1)[-1]

    @property
    def resource(self) -> str:
        return self.id.rsplit(".", 1)[0]

    @property
    def is_write(self) -> bool:
        if self.http_method not in WRITE_HTTP:
            return False
        return self.name not in READ_POST_NAMES and not self.name.startswith(READ_POST_PREFIXES)

    @property
    def is_delete(self) -> bool:
        return self.http_method == "DELETE"

    @property
    def supports_validate_only(self) -> bool:
        return "validateOnly" in self.parameters

    @property
    def required(self) -> list[str]:
        return sorted(n for n, p in self.parameters.items() if p.get("required"))


def _walk(node: dict[str, Any]) -> list[dict[str, Any]]:
    found = list(node.get("methods", {}).values())
    for child in node.get("resources", {}).values():
        found += _walk(child)
    return found


def _method(raw: dict[str, Any]) -> Method:
    request = raw.get("request") or {}
    return Method(
        id=str(raw["id"]),
        http_method=str(raw.get("httpMethod", "GET")),
        path=str(raw.get("flatPath") or raw.get("path", "")),
        parameters=dict(raw.get("parameters", {})),
        request_ref=request.get("$ref"),
        description=str(raw.get("description", "")).strip(),
        scopes=tuple(raw.get("scopes", ())),
    )


def all_methods(doc: dict[str, Any]) -> list[Method]:
    return sorted((_method(m) for m in _walk(doc)), key=lambda m: m.id)


def find_method(doc: dict[str, Any], method_id: str) -> Method:
    """A method by full id (``tagmanager.accounts.containers.create``) or without the API prefix."""
    # Ids carry the API's own prefix, which can differ from the document name
    # (searchconsole publishes ``webmasters.sites.list``), so match with or without it.
    methods = all_methods(doc)
    method_id = re.sub(r"^v[0-9][\w.]*:", "", method_id.strip())  # "v1beta:properties..." -> ...
    for method in methods:
        if method_id in (method.id, method.id.split(".", 1)[-1]):
            return method
    resource = method_id.rsplit(".", 1)[0]
    near = [m.id for m in methods if m.resource == resource or m.resource.endswith("." + resource)]
    if not near:
        ids = [m.id for m in methods]
        near = difflib.get_close_matches(
            method_id, ids, n=3, cutoff=0.5
        ) or difflib.get_close_matches(
            method_id, [i.split(".", 1)[-1] for i in ids], n=3, cutoff=0.5
        )
    hint = f"; did you mean: {', '.join(near)}" if near else ""
    raise InvalidCall(
        f"unknown method {method_id!r} in {doc.get('name')} {doc.get('version')}{hint}"
    )


def sibling(doc: dict[str, Any], method: Method, name: str) -> Method | None:
    """Another method on the same resource (e.g. the ``get`` next to a ``patch``)."""
    try:
        return find_method(doc, f"{method.resource}.{name}")
    except InvalidCall:
        return None


def scope_gap(method: Method, granted: set[str]) -> list[str]:
    """The scopes that would authorize ``method`` when the token holds none of them, else []."""
    if not method.scopes or granted & set(method.scopes):
        return []
    return sorted(method.scopes)


def describe(method: Method, *, summary_chars: int = 160) -> dict[str, object]:
    first = method.description.split("\n", 1)[0][:summary_chars]
    return {
        "method": method.id,
        "http": method.http_method,
        "write": method.is_write,
        "required": method.required,
        "validate_only": method.supports_validate_only,
        "summary": first,
    }


def schema_fields(doc: dict[str, Any], ref: str | None) -> dict[str, str]:
    """Top-level fields of a schema with their type (``$ref`` name for nested objects)."""
    schema = doc.get("schemas", {}).get(ref or "", {})
    out: dict[str, str] = {}
    for name, prop in schema.get("properties", {}).items():
        kind = prop.get("$ref") or prop.get("type", "any")
        if prop.get("type") == "array":
            item = prop.get("items", {})
            kind = f"array<{item.get('$ref') or item.get('type', 'any')}>"
        if str(prop.get("description", "")).startswith("Output only"):
            kind += " (output only)"
        out[name] = kind
    return out


def _check_param(name: str, spec: dict[str, Any], value: object) -> None:
    values = value if spec.get("repeated") and isinstance(value, list) else [value]
    for item in values:
        enum = spec.get("enum")
        if enum and str(item) not in enum:
            raise InvalidCall(f"parameter {name!r}: {item!r} is not one of {enum}")
        pattern = spec.get("pattern")
        if pattern and spec.get("location") == "path" and not re.fullmatch(pattern, str(item)):
            raise InvalidCall(f"parameter {name!r}: {item!r} does not match {pattern}")


def _check_body(doc: dict[str, Any], ref: str, value: object, where: str, depth: int = 0) -> None:
    schema = doc.get("schemas", {}).get(ref)
    if schema is None or depth > 12:
        return
    _check_value(doc, schema, value, where, depth)


def _check_value(
    doc: dict[str, Any], schema: dict[str, Any], value: object, where: str, depth: int
) -> None:
    if "$ref" in schema:
        _check_body(doc, schema["$ref"], value, where, depth + 1)
        return
    kind = schema.get("type")
    if kind in _JSON_TYPES:
        # bool is an int subclass in Python; JSON keeps them apart.
        matches = isinstance(value, _JSON_TYPES[kind]) and (
            kind == "boolean" or not isinstance(value, bool)
        )
        if not matches:
            raise InvalidCall(f"{where}: expected {kind}, got {type(value).__name__}")
    if kind == "array" and isinstance(value, list):
        for index, item in enumerate(value):
            _check_value(doc, schema.get("items", {}), item, f"{where}[{index}]", depth + 1)
    if kind == "object" and isinstance(value, dict):
        properties = schema.get("properties")
        extra = schema.get("additionalProperties")
        for key, item in value.items():
            if properties and key in properties:
                _check_value(doc, properties[key], item, f"{where}.{key}", depth + 1)
            elif extra is not None:
                _check_value(doc, extra, item, f"{where}.{key}", depth + 1)
            elif properties is not None:
                known = ", ".join(sorted(properties))
                raise InvalidCall(f"{where}: unknown field {key!r} (known: {known})")
    elif kind == "string" and schema.get("enum") and value not in schema["enum"]:
        raise InvalidCall(f"{where}: {value!r} is not one of {schema['enum']}")


def validate_call(
    doc: dict[str, Any],
    method_id: str,
    params: dict[str, object] | None = None,
    body: dict[str, object] | None = None,
) -> Method:
    """The resolved method, or ``InvalidCall`` naming exactly what breaks the contract."""
    method = find_method(doc, method_id)
    params = dict(params or {})
    known = {**doc.get("parameters", {}), **method.parameters}
    unknown = sorted(set(params) - set(known))
    if unknown:
        fields = schema_fields(doc, method.request_ref)
        body_hint = (
            f"; request body fields go in `body` ({method.request_ref}: {', '.join(sorted(fields))})"
            if fields
            else ""
        )
        raise InvalidCall(
            f"{method.id}: unknown parameter(s) {unknown} "
            f"(URL parameters accepted: {sorted(method.parameters)}){body_hint}"
        )
    missing = [name for name in method.required if params.get(name) in (None, "")]
    if missing:
        raise InvalidCall(f"{method.id}: missing required parameter(s) {missing}")
    for name, value in params.items():
        _check_param(name, known[name], value)
    if body is not None:
        if method.request_ref is None:
            raise InvalidCall(f"{method.id} takes no request body")
        if not isinstance(body, dict):
            raise InvalidCall(f"{method.id}: body must be a JSON object")
        _check_body(doc, method.request_ref, body, "body")
    return method
