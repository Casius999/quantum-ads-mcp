"""Discovery-contract validation and rollback derivation, on a small hand-written document."""

from __future__ import annotations

import pytest

from quantum_ads.connectors.googleapi import discovery, rollback
from quantum_ads.connectors.googleapi.discovery import InvalidCall

NAME = {"type": "string", "location": "path", "required": True, "pattern": "^widgets/[^/]+$"}
DOC: dict[str, object] = {
    "name": "demo",
    "version": "v1",
    "parameters": {"fields": {"type": "string", "location": "query"}},
    "schemas": {
        "Widget": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Output only. Resource name."},
                "displayName": {"type": "string"},
                "size": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "labels": {"type": "object", "additionalProperties": {"type": "string"}},
                "child": {"$ref": "Child"},
                "children": {"type": "array", "items": {"$ref": "Child"}},
                "state": {"type": "string", "enum": ["ON", "OFF"]},
            },
        },
        "Child": {"type": "object", "properties": {"note": {"type": "string"}}},
        "ArchiveRequest": {"type": "object", "properties": {}},
    },
    "resources": {
        "widgets": {
            "methods": {
                "get": {
                    "id": "demo.widgets.get",
                    "httpMethod": "GET",
                    "parameters": {"name": NAME},
                },
                "list": {
                    "id": "demo.widgets.list",
                    "httpMethod": "GET",
                    "parameters": {
                        "view": {"type": "string", "location": "query", "enum": ["BASIC", "FULL"]},
                        "ids": {"type": "string", "location": "query", "repeated": True},
                    },
                    "description": "Lists widgets.\nMore detail.",
                },
                "create": {
                    "id": "demo.widgets.create",
                    "httpMethod": "POST",
                    "flatPath": "v1/widgets",
                    "parameters": {
                        "parent": {"type": "string", "location": "query", "required": True}
                    },
                    "request": {"$ref": "Widget"},
                },
                "patch": {
                    "id": "demo.widgets.patch",
                    "httpMethod": "PATCH",
                    "parameters": {
                        "name": NAME,
                        "updateMask": {"type": "string", "location": "query"},
                        "validateOnly": {"type": "boolean", "location": "query"},
                    },
                    "request": {"$ref": "Widget"},
                },
                "delete": {
                    "id": "demo.widgets.delete",
                    "httpMethod": "DELETE",
                    "parameters": {"name": NAME},
                },
                "search": {
                    "id": "demo.widgets.search",
                    "httpMethod": "POST",
                    "request": {"$ref": "Child"},
                },
                "analyzeText": {"id": "demo.widgets.analyzeText", "httpMethod": "POST"},
            },
            "resources": {
                "gadgets": {
                    "methods": {
                        "insert": {
                            "id": "demo.widgets.gadgets.insert",
                            "httpMethod": "POST",
                            "request": {"$ref": "Widget"},
                        },
                        "delete": {
                            "id": "demo.widgets.gadgets.delete",
                            "httpMethod": "DELETE",
                            "parameters": {
                                "id": {"type": "string", "location": "query", "required": True}
                            },
                        },
                    }
                }
            },
        },
        "things": {
            "methods": {
                "create": {"id": "demo.things.create", "httpMethod": "POST"},
                "archive": {
                    "id": "demo.things.archive",
                    "httpMethod": "POST",
                    "parameters": {
                        "name": {"type": "string", "location": "path", "required": True}
                    },
                    "request": {"$ref": "ArchiveRequest"},
                },
                "update": {"id": "demo.things.update", "httpMethod": "PUT"},
            }
        },
        "orphans": {
            "methods": {
                "create": {
                    "id": "demo.orphans.create",
                    "httpMethod": "POST",
                    "parameters": {"owner": {"type": "string", "location": "query"}},
                },
                "delete": {
                    "id": "demo.orphans.delete",
                    "httpMethod": "DELETE",
                    "parameters": {
                        "owner": {"type": "string", "location": "query", "required": True},
                        "slot": {"type": "string", "location": "query", "required": True},
                    },
                },
            }
        },
    },
}


def test_methods_are_classified_read_write_delete():
    methods = {m.id: m for m in discovery.all_methods(DOC)}
    assert len(methods) == 14
    assert not methods["demo.widgets.get"].is_write
    assert not methods["demo.widgets.search"].is_write  # reporting POST
    assert not methods["demo.widgets.analyzeText"].is_write  # analysis POST
    assert methods["demo.widgets.create"].is_write and not methods["demo.widgets.create"].is_delete
    assert methods["demo.widgets.delete"].is_delete
    assert methods["demo.widgets.patch"].supports_validate_only
    assert methods["demo.widgets.patch"].required == ["name"]


def test_find_method_accepts_short_ids_and_hints_on_typos():
    assert discovery.find_method(DOC, "widgets.get").id == "demo.widgets.get"
    with pytest.raises(InvalidCall, match="did you mean: .*demo.widgets.get"):
        discovery.find_method(DOC, "widgets.fetch")
    with pytest.raises(InvalidCall, match=r"unknown method 'nope.x' in demo v1$"):
        discovery.find_method(DOC, "nope.x")


def test_describe_and_schema_fields():
    listed = discovery.describe(discovery.find_method(DOC, "widgets.list"))
    assert listed == {
        "method": "demo.widgets.list",
        "http": "GET",
        "write": False,
        "required": [],
        "validate_only": False,
        "summary": "Lists widgets.",
    }
    fields = discovery.schema_fields(DOC, "Widget")
    assert fields["name"] == "string (output only)"
    assert fields["child"] == "Child" and fields["children"] == "array<Child>"
    assert fields["tags"] == "array<string>"
    assert discovery.schema_fields(DOC, None) == {}


def test_valid_call_passes_with_nested_body_and_global_params():
    body = {
        "displayName": "W",
        "size": "12",
        "enabled": True,
        "tags": ["a"],
        "labels": {"k": "v"},
        "child": {"note": "n"},
        "children": [{"note": "m"}],
        "state": "ON",
    }
    method = discovery.validate_call(DOC, "widgets.create", {"parent": "p", "fields": "name"}, body)
    assert method.id == "demo.widgets.create"
    assert discovery.validate_call(DOC, "widgets.list", {"view": "FULL", "ids": ["1", "2"]})


@pytest.mark.parametrize(
    ("method", "params", "body", "message"),
    [
        ("widgets.create", {}, None, "missing required parameter"),
        ("widgets.create", {"parent": "p", "bogus": 1}, None, "unknown parameter"),
        ("widgets.get", {"name": "gadgets/1"}, None, "does not match"),
        ("widgets.list", {"view": "ALL"}, None, "is not one of"),
        ("widgets.list", {"ids": ["1", "X"], "view": "nope"}, None, "is not one of"),
        ("widgets.get", {"name": "widgets/1"}, {"x": 1}, "takes no request body"),
        ("widgets.create", {"parent": "p"}, ["x"], "must be a JSON object"),
        ("widgets.create", {"parent": "p"}, {"colour": "red"}, "unknown field 'colour'"),
        ("widgets.create", {"parent": "p"}, {"size": True}, "expected integer, got bool"),
        ("widgets.create", {"parent": "p"}, {"enabled": "yes"}, "expected boolean"),
        ("widgets.create", {"parent": "p"}, {"tags": "a"}, "expected array"),
        (
            "widgets.create",
            {"parent": "p"},
            {"labels": {"k": 1}},
            r"body.labels.k: expected string",
        ),
        ("widgets.create", {"parent": "p"}, {"child": {"x": 1}}, r"body.child: unknown field"),
        ("widgets.create", {"parent": "p"}, {"children": [{"note": 2}]}, r"children\[0\].note"),
        ("widgets.create", {"parent": "p"}, {"state": "MAYBE"}, "is not one of"),
    ],
)
def test_contract_violations_are_named(method, params, body, message):
    with pytest.raises(InvalidCall, match=message):
        discovery.validate_call(DOC, method, params, body)


def test_unknown_schema_refs_are_not_checked():
    doc = {**DOC, "schemas": {}}
    assert discovery.validate_call(doc, "widgets.create", {"parent": "p"}, {"anything": 1})


def test_update_reads_before_state_and_restores_masked_fields():
    patch = discovery.find_method(DOC, "widgets.patch")
    params: dict[str, object] = {"name": "widgets/1", "updateMask": "displayName,child.note"}
    getter, get_params = rollback.before_state_call(DOC, patch, params)  # type: ignore[misc]
    assert getter.id == "demo.widgets.get" and get_params == {"name": "widgets/1"}
    before = {"name": "widgets/1", "displayName": "Old", "child": {"note": "x"}, "size": 3}
    inverse = rollback.inverse_operations(DOC, "demo", "v1", patch, params, {}, before)
    assert inverse == [
        {
            "api": "demo",
            "version": "v1",
            "method": "demo.widgets.patch",
            "params": params,
            "body": {"child": {"note": "x"}, "displayName": "Old"},
        }
    ]
    unmasked = rollback.inverse_of_update("demo", "v1", patch, {"name": "widgets/1"}, before)
    assert unmasked["body"] == before
    listed_mask = rollback.inverse_of_update(
        "demo", "v1", patch, {"name": "widgets/1", "update_mask": ["size"]}, before
    )
    assert listed_mask["body"] == {"size": 3}


def test_before_state_is_skipped_when_it_cannot_be_read():
    patch = discovery.find_method(DOC, "widgets.patch")
    assert rollback.before_state_call(DOC, patch, {}) is None  # get needs name
    assert rollback.before_state_call(DOC, discovery.find_method(DOC, "things.update"), {}) is None
    create = discovery.find_method(DOC, "widgets.create")
    assert rollback.before_state_call(DOC, create, {"parent": "p"}) is None


def test_create_records_delete_or_archive():
    create = discovery.find_method(DOC, "widgets.create")
    inverse = rollback.inverse_operations(
        DOC, "demo", "v1", create, {"parent": "p"}, {"name": "widgets/9"}, None
    )
    assert inverse == [
        {
            "api": "demo",
            "version": "v1",
            "method": "demo.widgets.delete",
            "params": {"name": "widgets/9"},
            "body": None,
        }
    ]
    insert = discovery.find_method(DOC, "widgets.gadgets.insert")
    by_id = rollback.inverse_of_create(DOC, "demo", "v1", insert, {}, {"id": "g1"})
    assert by_id is not None and by_id["params"] == {"id": "g1"}
    archived = rollback.inverse_of_create(
        DOC, "demo", "v1", discovery.find_method(DOC, "things.create"), {}, {"name": "things/1"}
    )
    assert archived is not None and archived["method"] == "demo.things.archive"
    assert archived["body"] == {}


def test_irreversible_writes_record_nothing():
    delete = discovery.find_method(DOC, "widgets.delete")
    assert (
        rollback.inverse_operations(DOC, "demo", "v1", delete, {"name": "widgets/1"}, {}, None)
        == []
    )
    create = discovery.find_method(DOC, "widgets.create")
    assert rollback.inverse_of_create(DOC, "demo", "v1", create, {"parent": "p"}, {}) is None
    insert = discovery.find_method(DOC, "widgets.gadgets.insert")
    assert rollback.inverse_of_create(DOC, "demo", "v1", insert, {}, {}) is None
    orphan = discovery.find_method(DOC, "orphans.create")
    resolved = rollback.inverse_of_create(
        DOC, "demo", "v1", orphan, {"owner": "o"}, {"slotId": "s"}
    )
    assert resolved is None  # 'slot' is neither in params nor an id field of the response
    no_delete = discovery.find_method(DOC, "widgets.search")
    assert rollback.inverse_of_create(DOC, "demo", "v1", no_delete, {}, {"name": "x"}) is None
    gadgets = {
        **DOC,
        "resources": {"g": {"methods": {"create": {"id": "demo.g.create", "httpMethod": "POST"}}}},
    }
    lone = discovery.find_method(gadgets, "g.create")
    assert rollback.inverse_of_create(gadgets, "demo", "v1", lone, {}, {"name": "g/1"}) is None


def test_create_inverse_takes_a_resource_id_from_the_response():
    doc = {
        "name": "demo",
        "resources": {
            "pins": {
                "methods": {
                    "create": {"id": "demo.pins.create", "httpMethod": "POST"},
                    "delete": {
                        "id": "demo.pins.delete",
                        "httpMethod": "DELETE",
                        "parameters": {"pinId": {"location": "path", "required": True}},
                    },
                }
            }
        },
    }
    create = discovery.find_method(doc, "pins.create")
    inverse = rollback.inverse_of_create(doc, "demo", "v1", create, {}, {"pinId": "p1"})
    assert inverse is not None and inverse["params"] == {"pinId": "p1"}


def test_update_without_mask_restores_only_the_fields_it_sent():
    patch = discovery.find_method(DOC, "widgets.patch")
    before = {"name": "widgets/1", "kind": "demo#widget", "displayName": "Old", "size": 3}
    inverse = rollback.inverse_operations(
        DOC, "demo", "v1", patch, {"name": "widgets/1"}, {}, before, {"displayName": "New"}
    )
    assert inverse[0]["body"] == {"displayName": "Old"}


def test_id_suffixed_delete_param_falls_back_to_the_response_id():
    doc = {
        "name": "drive",
        "resources": {
            "files": {
                "methods": {
                    "create": {"id": "drive.files.create", "httpMethod": "POST"},
                    "delete": {
                        "id": "drive.files.delete",
                        "httpMethod": "DELETE",
                        "parameters": {"fileId": {"location": "path", "required": True}},
                    },
                }
            }
        },
    }
    create = discovery.find_method(doc, "files.create")
    inverse = rollback.inverse_of_create(doc, "drive", "v3", create, {}, {"id": "abc"})
    assert inverse is not None and inverse["params"] == {"fileId": "abc"}


def test_methods_match_with_a_prefix_that_differs_from_the_document_name():
    doc = {
        "name": "searchconsole",
        "resources": {
            "sites": {"methods": {"list": {"id": "webmasters.sites.list", "httpMethod": "GET"}}},
            "searchanalytics": {
                "methods": {
                    "query": {"id": "webmasters.searchanalytics.query", "httpMethod": "POST"}
                }
            },
        },
    }
    assert discovery.find_method(doc, "sites.list").id == "webmasters.sites.list"
    assert discovery.find_method(doc, "webmasters.sites.list").id == "webmasters.sites.list"
    assert not discovery.find_method(doc, "searchanalytics.query").is_write


def test_scope_gap_names_the_scopes_a_token_lacks():
    method = discovery.Method("x.y.z", "POST", "", {}, None, "", scopes=("a", "b"))
    assert discovery.scope_gap(method, {"b", "c"}) == []
    assert discovery.scope_gap(method, {"c"}) == ["a", "b"]
    assert discovery.scope_gap(discovery.Method("x.y.z", "GET", "", {}, None, ""), set()) == []


def test_errors_teach_the_agent_how_to_fix_the_call():
    assert discovery.find_method(DOC, "v1:widgets.get").id == "demo.widgets.get"
    with pytest.raises(InvalidCall, match=r"did you mean: demo.widgets.gadgets.insert"):
        discovery.find_method(DOC, "gadget.insrt")
    with pytest.raises(
        InvalidCall, match=r"request body fields go in `body` \(Widget: .*displayName"
    ):
        discovery.validate_call(DOC, "widgets.create", {"parent": "p", "displayName": "x"})
    with pytest.raises(InvalidCall) as no_body:
        discovery.validate_call(DOC, "widgets.get", {"name": "widgets/1", "x": 1})
    assert "body" not in str(no_body.value)


def test_method_fields_come_from_the_document():
    raw = {
        "name": "d",
        "resources": {
            "r": {
                "methods": {
                    "flat": {
                        "id": "d.r.flat",
                        "flatPath": "v1/r/{id}",
                        "path": "v1/{+name}",
                        "scopes": ["s1", "s2"],
                    },
                    "plain": {
                        "id": "d.r.plain",
                        "path": "v1/{+name}",
                        "description": "One.\nTwo.\nThree.",
                    },
                    "bare": {"id": "d.r.bare"},
                }
            }
        },
    }
    flat, plain, bare = (discovery.find_method(raw, f"r.{n}") for n in ("flat", "plain", "bare"))
    assert flat.path == "v1/r/{id}" and flat.scopes == ("s1", "s2")
    assert plain.path == "v1/{+name}" and discovery.describe(plain)["summary"] == "One."
    assert (
        bare.path == ""
        and bare.http_method == "GET"
        and bare.description == ""
        and bare.scopes == ()
    )
    # A document without global parameters still validates.
    assert discovery.validate_call(raw, "r.bare", {}).id == "d.r.bare"


def test_an_empty_required_value_counts_as_missing():
    with pytest.raises(InvalidCall, match=r"missing required parameter\(s\) \['parent'\]"):
        discovery.validate_call(DOC, "widgets.create", {"parent": ""})


def test_error_lists_are_comma_separated():
    with pytest.raises(InvalidCall, match=r"known: child, children, displayName, enabled, labels"):
        discovery.validate_call(DOC, "widgets.create", {"parent": "p"}, {"zzz": 1})
    with pytest.raises(InvalidCall, match=r"\(Widget: child, children, displayName"):
        discovery.validate_call(DOC, "widgets.create", {"parent": "p", "zzz": 1})


def test_schema_fields_without_item_type_or_description():
    doc = {
        "schemas": {
            "S": {
                "properties": {"a": {"type": "array", "items": {}}, "b": {}, "c": {"type": "array"}}
            }
        }
    }
    assert discovery.schema_fields(doc, "S") == {"a": "array<any>", "b": "any", "c": "array<any>"}


def test_update_mask_wins_over_the_body_keys():
    patch = discovery.find_method(DOC, "widgets.patch")
    before = {"displayName": "Old", "size": 3}
    inverse = rollback.inverse_of_update(
        "demo",
        "v1",
        patch,
        {"name": "widgets/1", "updateMask": "size"},
        before,
        {"displayName": "x"},
    )
    assert inverse["body"] == {"size": 3}


def test_create_inverse_mixes_response_ids_and_call_params():
    orphan = discovery.find_method(DOC, "orphans.create")
    inverse = rollback.inverse_operations(
        DOC, "demo", "v1", orphan, {"owner": "o"}, {"slot": "s1"}, None
    )
    assert inverse[0]["params"] == {"owner": "o", "slot": "s1"}
    # An empty identifier in the response is not used; the call's own parameter is.
    blank = rollback.inverse_of_create(
        DOC, "demo", "v1", orphan, {"owner": "o", "slot": "s2"}, {"slot": ""}
    )
    assert blank is not None and blank["params"]["slot"] == "s2"
    # A response "id" only fills parameters named like an id.
    assert (
        rollback.inverse_of_create(DOC, "demo", "v1", orphan, {"owner": "o"}, {"id": "9"}) is None
    )
