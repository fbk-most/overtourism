# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest


def _raise_runtime_error(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("path", "params", "expected_call", "expected_body"),
    [
        (
            "/data/overtourism/indexes/categories",
            {"language": "en"},
            ("categories", {"language": "en"}),
            {"language": "en", "categories": ["pressure", "services"]},
        ),
        (
            "/data/overtourism/indexes/list",
            {"category": "pressure", "language": "it"},
            ("list", {"category": "pressure", "language": "it"}),
            {"category": "pressure", "language": "it", "indexes": ["visits"]},
        ),
        (
            "/data/overtourism/indexes/data",
            {"dataframe": "presence"},
            ("dataframe", {"dataframe": "presence"}),
            {"dataframe": "presence", "rows": [{"value": 1}]},
        ),
        (
            "/data/overtourism/indexes/map",
            {"map": "districts"},
            ("map", {"map": "districts"}),
            {"map": "districts", "features": [{"id": "feature-1"}]},
        ),
    ],
)
def test_data_routes_delegate_to_the_loader(
    client,
    data_loader,
    tenant: str,
    path: str,
    params: dict,
    expected_call: tuple[str, dict],
    expected_body: dict,
) -> None:
    response = client.get(f"/api/v2/{tenant}{path}", params=params)

    assert response.status_code == 200
    assert response.json() == expected_body
    assert data_loader.calls[-1] == expected_call


def test_list_widgets_uses_the_viewer(client, tenant: str, viewer) -> None:
    response = client.get(f"/api/v2/{tenant}/widgets", params={"language": "en"})

    assert response.status_code == 200
    assert response.json() == {
        "widgets": {
            "summary": {
                "language": "en",
                "values": {},
            }
        }
    }
    assert viewer.widget_calls[-1] == ({}, "en")


def test_problem_routes_accept_typed_domain_fields(
    client,
    tenant: str,
    viewer,
) -> None:
    response = client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "name": "Lake Cleanup",
            "description": "Reduce visitor pressure",
            "extras": {
                "groups": ["pressure"],
                "objective": "Keep the shoreline usable",
                "links": ["https://example.test/lake"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["extras"] == {
        "groups": ["pressure"],
        "objective": "Keep the shoreline usable",
        "links": ["https://example.test/lake"],
        "editable_indexes": ["pressure-widget"],
    }
    assert viewer.group_calls[-1] == ["pressure"]


def test_problem_updates_preserve_current_groups_when_request_omits_domain_fields(
    client,
    tenant: str,
    viewer,
) -> None:
    create_response = client.post(
        f"/api/v2/{tenant}/problems",
        json={
            "name": "Lake Cleanup",
            "description": "Reduce visitor pressure",
            "extras": {
                "groups": ["pressure"],
                "objective": "Keep the shoreline usable",
            },
        },
    )
    assert create_response.status_code == 200

    update_response = client.put(
        f"/api/v2/{tenant}/problems/lake-cleanup",
        json={
            "version": create_response.json()["version"],
            "name": "Lake Cleanup Updated",
            "description": "Still reducing pressure",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["extras"] == {
        "groups": ["pressure"],
        "objective": "Keep the shoreline usable",
        "editable_indexes": ["pressure-widget"],
    }
    assert viewer.group_calls[-1] == ["pressure"]


def test_problem_routes_expose_typed_domain_fields_in_openapi(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    post_request = openapi["paths"]["/api/v2/{tenant}/problems"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]
    put_request = openapi["paths"]["/api/v2/{tenant}/problems/{problem_id}"]["put"][
        "requestBody"
    ]["content"]["application/json"]["schema"]

    post_schema = openapi["components"]["schemas"][
        post_request["$ref"].rsplit("/", 1)[-1]
    ]
    put_schema = openapi["components"]["schemas"][
        put_request["$ref"].rsplit("/", 1)[-1]
    ]

    assert set(post_schema["properties"]) >= {
        "name",
        "description",
        "extras",
    }
    assert set(put_schema["properties"]) >= {
        "version",
        "name",
        "description",
        "extras",
    }


def test_domain_routes_return_500_for_failing_collaborators(
    client,
    error_client,
    handler,
    tenant: str,
) -> None:
    handler.data_loader = None
    no_loader_response = error_client.get(
        f"/api/v2/{tenant}/data/overtourism/indexes/categories"
    )
    assert no_loader_response.status_code == 500

    class BrokenLoader:
        get_categories = staticmethod(_raise_runtime_error)
        get_list = staticmethod(_raise_runtime_error)
        get_dataframe = staticmethod(_raise_runtime_error)
        get_map = staticmethod(_raise_runtime_error)

    handler.data_loader = BrokenLoader()
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/categories"
        ).status_code
        == 500
    )
    assert (
        error_client.get(f"/api/v2/{tenant}/data/overtourism/indexes/list").status_code
        == 500
    )
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/data",
            params={"dataframe": "presence"},
        ).status_code
        == 500
    )
    assert (
        error_client.get(
            f"/api/v2/{tenant}/data/overtourism/indexes/map",
            params={"map": "districts"},
        ).status_code
        == 500
    )

    handler.get_widgets_fn = None
    empty_widget_response = client.get(f"/api/v2/{tenant}/widgets")
    assert empty_widget_response.status_code == 200
    assert empty_widget_response.json() == {"widgets": {}}

    class BrokenViewer:
        @staticmethod
        def get_widgets(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

    handler.get_widgets_fn = BrokenViewer.get_widgets
    widget_response = error_client.get(f"/api/v2/{tenant}/widgets")
    assert widget_response.status_code == 500
