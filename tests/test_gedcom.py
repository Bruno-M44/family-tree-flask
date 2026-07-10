import io

import pytest

from app.views.gedcom_view import (
    _compute_generations,
    _extract_indi,
    _ged_date,
    _parse_ged_date,
    _parse_gedcom,
)


# ---------------------------------------------------------------------------
# Unit tests: pure helpers
# ---------------------------------------------------------------------------

def test_ged_date_formats_correctly():
    from datetime import datetime
    assert _ged_date(datetime(1990, 1, 5)) == "05 JAN 1990"


def test_ged_date_none_is_none():
    assert _ged_date(None) is None


@pytest.mark.parametrize("raw,expected", [
    ("05 JAN 1990", (1990, 1, 5)),
    ("JAN 1990", (1990, 1, 1)),
    ("1990", (1990, 1, 1)),
])
def test_parse_ged_date_variants(raw, expected):
    d = _parse_ged_date(raw)
    assert (d.year, d.month, d.day) == expected


def test_parse_ged_date_invalid_returns_none():
    assert _parse_ged_date("not a date") is None
    assert _parse_ged_date("") is None


def test_parse_gedcom_builds_nested_structure():
    text = "\n".join([
        "0 @I1@ INDI",
        "1 NAME John /Smith/",
        "1 BIRT",
        "2 DATE 01 JAN 1950",
        "0 TRLR",
    ])
    records = _parse_gedcom(text)
    assert len(records) == 2
    indi = records[0]
    assert indi["tag"] == "INDI"
    assert indi["xref"] == "@I1@"
    name_node = indi["children"][0]
    assert name_node["tag"] == "NAME"
    assert name_node["value"] == "John /Smith/"
    birt_node = indi["children"][1]
    assert birt_node["children"][0]["tag"] == "DATE"
    assert birt_node["children"][0]["value"] == "01 JAN 1950"


def test_extract_indi_parses_givn_surn():
    text = "\n".join([
        "0 @I1@ INDI",
        "1 NAME John /Smith/",
        "2 GIVN John",
        "2 SURN Smith",
        "1 SEX M",
    ])
    node = _parse_gedcom(text)[0]
    data = _extract_indi(node)
    assert data["surnames"] == "John"
    assert data["name"] == "Smith"
    assert data["sexe"] == "M"


def test_extract_indi_falls_back_to_raw_name_when_no_givn_surn():
    text = "\n".join([
        "0 @I1@ INDI",
        "1 NAME John /Smith/",
    ])
    node = _parse_gedcom(text)[0]
    data = _extract_indi(node)
    assert data["surnames"] == "John"
    assert data["name"] == "Smith"


def test_compute_generations_simple_parent_child():
    families = [{"husb": "@I1@", "wife": "@I2@", "chil": ["@I3@"]}]
    xrefs = {"@I1@", "@I2@", "@I3@"}
    gens = _compute_generations(xrefs, families)
    assert gens["@I1@"] == 0
    assert gens["@I2@"] == 0
    assert gens["@I3@"] == 1


def test_compute_generations_handles_cycles_without_crashing():
    # Malformed/cyclic data (child is also listed as its own parent) must not
    # cause infinite recursion.
    families = [{"husb": "@I1@", "wife": None, "chil": ["@I1@"]}]
    gens = _compute_generations({"@I1@"}, families)
    assert "@I1@" in gens


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def family_tree_id(client, auth_headers):
    response = client.post("/family_tree", json={"title": "Test Tree", "family_name": "Test"}, headers=auth_headers)
    assert response.status_code == 201
    return response.get_json()["data"]["id_family_tree"]


def test_export_gedcom_unauthenticated(client, family_tree_id):
    response = client.get(f"/family_trees/{family_tree_id}/export/gedcom")
    assert response.status_code == 401


def test_export_gedcom_not_found_for_foreign_tree(client, auth_headers):
    response = client.get("/family_trees/99999/export/gedcom", headers=auth_headers)
    assert response.status_code == 404


def test_export_gedcom_contains_individual_and_family_records(client, auth_headers, family_tree_id):
    parent1 = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Smith", "surnames": "John", "generation": 0, "sexe": "M", "birthday": "01/01/1950"},
        headers=auth_headers,
    ).get_json()["data"]
    parent2 = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Smith", "surnames": "Jane", "generation": 0, "sexe": "F"},
        headers=auth_headers,
    ).get_json()["data"]
    child = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Smith", "surnames": "Bob", "generation": 1, "parents": [parent1["id_family_tree_cell"], parent2["id_family_tree_cell"]]},
        headers=auth_headers,
    ).get_json()["data"]
    couple_resp = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells/{parent1['id_family_tree_cell']}/couple",
        json={"partner_id": parent2["id_family_tree_cell"]},
        headers=auth_headers,
    )
    assert couple_resp.status_code == 201

    response = client.get(f"/family_trees/{family_tree_id}/export/gedcom", headers=auth_headers)
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    text = response.get_data(as_text=True)
    assert "0 HEAD" in text
    assert "0 TRLR" in text
    assert text.count("INDI") == 3
    assert "1 NAME John /Smith/" in text
    assert "1 SEX M" in text
    assert "0 @F1@ FAM" in text
    assert f"1 CHIL @I{child['id_family_tree_cell']}@" in text


def test_import_gedcom_missing_file(client, auth_headers):
    response = client.post("/family_trees/import/gedcom", headers=auth_headers)
    assert response.status_code == 400


def test_import_gedcom_unauthenticated(client):
    data = {"file": (io.BytesIO(b"0 HEAD\n0 TRLR"), "tree.ged")}
    response = client.post("/family_trees/import/gedcom", data=data, content_type="multipart/form-data")
    assert response.status_code == 401


def test_import_gedcom_creates_tree_with_relations(client, auth_headers):
    ged = "\n".join([
        "0 HEAD",
        "0 @I1@ INDI",
        "1 NAME John /Smith/",
        "2 GIVN John",
        "2 SURN Smith",
        "1 SEX M",
        "0 @I2@ INDI",
        "1 NAME Jane /Smith/",
        "2 GIVN Jane",
        "2 SURN Smith",
        "1 SEX F",
        "0 @I3@ INDI",
        "1 NAME Bob /Smith/",
        "2 GIVN Bob",
        "2 SURN Smith",
        "1 SEX M",
        "0 @F1@ FAM",
        "1 HUSB @I1@",
        "1 WIFE @I2@",
        "1 CHIL @I3@",
        "1 MARR",
        "2 DATE 01 JUN 1975",
        "0 TRLR",
    ])
    data = {"file": (io.BytesIO(ged.encode("utf-8")), "tree.ged")}
    response = client.post(
        "/family_trees/import/gedcom", data=data, headers=auth_headers, content_type="multipart/form-data",
    )
    assert response.status_code == 201
    id_family_tree = response.get_json()["id_family_tree"]

    cells_response = client.get(f"/family_trees/{id_family_tree}/family_tree_cells", headers=auth_headers)
    cells = cells_response.get_json()["data"]
    assert len(cells) == 3
    bob = next(c for c in cells if c["surnames"] == "Bob")
    assert bob["orphan"] is False
    assert len(bob["children"]) == 0
    john = next(c for c in cells if c["surnames"] == "John")
    assert any(c["surnames"] == "Bob" for c in john["children"])
    assert any(c["surnames"] == "Jane" for c in john["couples"])


def test_export_then_import_round_trip_preserves_structure(client, auth_headers, family_tree_id):
    """Export a tree built via the normal API, re-import the resulting GEDCOM,
    and check the imported tree has the same shape (individuals + relations)."""
    parent1 = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Dupont", "surnames": "Alice", "generation": 0, "sexe": "F"},
        headers=auth_headers,
    ).get_json()["data"]
    parent2 = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Martin", "surnames": "Bruno", "generation": 0, "sexe": "M"},
        headers=auth_headers,
    ).get_json()["data"]
    client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Dupont", "surnames": "Celeste", "generation": 1, "parents": [parent1["id_family_tree_cell"], parent2["id_family_tree_cell"]]},
        headers=auth_headers,
    )
    couple_resp = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells/{parent1['id_family_tree_cell']}/couple",
        json={"partner_id": parent2["id_family_tree_cell"]},
        headers=auth_headers,
    )
    assert couple_resp.status_code == 201

    export_response = client.get(f"/family_trees/{family_tree_id}/export/gedcom", headers=auth_headers)
    assert export_response.status_code == 200
    ged_bytes = export_response.get_data()

    import_response = client.post(
        "/family_trees/import/gedcom",
        data={"file": (io.BytesIO(ged_bytes), "export.ged")},
        headers=auth_headers,
        content_type="multipart/form-data",
    )
    assert import_response.status_code == 201
    imported_id = import_response.get_json()["id_family_tree"]

    imported_cells = client.get(
        f"/family_trees/{imported_id}/family_tree_cells", headers=auth_headers,
    ).get_json()["data"]
    assert len(imported_cells) == 3
    surnames = {c["surnames"] for c in imported_cells}
    assert surnames == {"Alice", "Bruno", "Celeste"}
    celeste = next(c for c in imported_cells if c["surnames"] == "Celeste")
    assert len(celeste["children"]) == 0
    assert celeste["orphan"] is False
    alice = next(c for c in imported_cells if c["surnames"] == "Alice")
    assert any(c["surnames"] == "Bruno" for c in alice["couples"])
    assert any(c["surnames"] == "Celeste" for c in alice["children"])
