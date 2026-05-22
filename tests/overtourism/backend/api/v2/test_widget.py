# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


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
