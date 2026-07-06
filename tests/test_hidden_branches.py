import pytest
from flask.testing import FlaskClient

from app import db as _db
from app.models import FamilyTreeCell, FamilyTreeHiddenBranches, association_user_ft
from sqlalchemy import insert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def family_tree_id(client: FlaskClient, auth_headers: dict) -> int:
    response = client.post(
        "/family_tree",
        json={"title": "Test Tree", "family_name": "Test"},
        headers=auth_headers,
    )
    return response.get_json()["data"]["id_family_tree"]


@pytest.fixture
def cell_id(client: FlaskClient, auth_headers: dict, family_tree_id: int) -> int:
    """Create one FamilyTreeCell in the tree and return its ID."""
    response = client.post(
        f"/family_trees/{family_tree_id}/family_tree_cells",
        json={"name": "Dupont", "surnames": "Alice", "generation": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()["data"]["id_family_tree_cell"]


# ---------------------------------------------------------------------------
# GET /family_trees/<id>/hidden_branches
# ---------------------------------------------------------------------------

def test_get_hidden_branches_empty(
    client: FlaskClient, auth_headers: dict, family_tree_id: int
) -> None:
    """Returns empty lists when no row exists yet."""
    response = client.get(
        f"/family_trees/{family_tree_id}/hidden_branches",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == []
    assert data["hidden_below"] == []


def test_get_hidden_branches_returns_stored_values(
    client: FlaskClient, auth_headers: dict, family_tree_id: int, cell_id: int
) -> None:
    """Returns previously saved values."""
    client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [cell_id], "hidden_below": []},
        headers=auth_headers,
    )
    response = client.get(
        f"/family_trees/{family_tree_id}/hidden_branches",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == [cell_id]
    assert data["hidden_below"] == []


def test_get_hidden_branches_non_member(
    client: FlaskClient, family_tree_id: int
) -> None:
    """A user who is not a member of the tree gets 403."""
    # Create and login a second user
    client.post("/user", json={
        "name": "Other", "surname": "User",
        "email": "other@test.com", "password": "pw",
    })
    from app.models import User
    user = User.query.filter_by(email="other@test.com").first()
    user.verified = True
    _db.session.commit()
    login = client.post("/login", json={"email": "other@test.com", "password": "pw"})
    other_headers = {"Authorization": f"Bearer {login.get_json()['data']}"}

    response = client.get(
        f"/family_trees/{family_tree_id}/hidden_branches",
        headers=other_headers,
    )
    assert response.status_code == 403


def test_get_hidden_branches_unauthenticated(
    client: FlaskClient, family_tree_id: int
) -> None:
    response = client.get(f"/family_trees/{family_tree_id}/hidden_branches")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /family_trees/<id>/hidden_branches
# ---------------------------------------------------------------------------

def test_put_hidden_branches_creates_row(
    client: FlaskClient, auth_headers: dict, family_tree_id: int, cell_id: int
) -> None:
    """First PUT creates a new row for the user/tree pair."""
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": [cell_id]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == []
    assert data["hidden_below"] == [cell_id]


def test_put_hidden_branches_updates_existing_row(
    client: FlaskClient, auth_headers: dict, family_tree_id: int, cell_id: int
) -> None:
    """Second PUT overwrites the previous values."""
    client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [cell_id], "hidden_below": []},
        headers=auth_headers,
    )
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": [cell_id]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == []
    assert data["hidden_below"] == [cell_id]


def test_put_hidden_branches_empty_lists(
    client: FlaskClient, auth_headers: dict, family_tree_id: int
) -> None:
    """PUT with empty lists is accepted and clears any previous values."""
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": []},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == []
    assert data["hidden_below"] == []


def test_put_hidden_branches_omitted_fields_default_to_empty(
    client: FlaskClient, auth_headers: dict, family_tree_id: int
) -> None:
    """PUT with no body treats both lists as empty."""
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["hidden_above"] == []
    assert data["hidden_below"] == []


def test_put_hidden_branches_invalid_ids_type(
    client: FlaskClient, auth_headers: dict, family_tree_id: int
) -> None:
    """Non-integer values in the lists return 400."""
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": ["not-an-int"], "hidden_below": []},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "integers" in response.get_json()["message"]


def test_put_hidden_branches_unknown_cell_ids(
    client: FlaskClient, auth_headers: dict, family_tree_id: int
) -> None:
    """Cell IDs that do not belong to the tree return 400."""
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [99999], "hidden_below": []},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Unknown cell IDs" in response.get_json()["message"]


def test_put_hidden_branches_non_member(
    client: FlaskClient, family_tree_id: int
) -> None:
    """A user who is not a member of the tree gets 403."""
    client.post("/user", json={
        "name": "Other", "surname": "User2",
        "email": "other2@test.com", "password": "pw",
    })
    from app.models import User
    user = User.query.filter_by(email="other2@test.com").first()
    user.verified = True
    _db.session.commit()
    login = client.post("/login", json={"email": "other2@test.com", "password": "pw"})
    other_headers = {"Authorization": f"Bearer {login.get_json()['data']}"}

    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": []},
        headers=other_headers,
    )
    assert response.status_code == 403


def test_put_hidden_branches_unauthenticated(
    client: FlaskClient, family_tree_id: int
) -> None:
    response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": []},
    )
    assert response.status_code == 401


def test_put_hidden_branches_isolation_between_users(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    cell_id: int,
) -> None:
    """Each user's hidden branches are stored independently."""
    # Create a second user and add them to the tree as editor
    # (viewers cannot PUT hidden branches, see test_put_hidden_branches_forbidden_for_viewer)
    client.post("/user", json={
        "name": "Second", "surname": "Member",
        "email": "second@test.com", "password": "pw2",
    })
    from app.models import User
    user2 = User.query.filter_by(email="second@test.com").first()
    user2.verified = True
    _db.session.commit()
    _db.session.execute(
        insert(association_user_ft).values(
            id_user=user2.id_user,
            id_family_tree=family_tree_id,
            role="editor",
        )
    )
    _db.session.commit()
    login2 = client.post("/login", json={"email": "second@test.com", "password": "pw2"})
    headers2 = {"Authorization": f"Bearer {login2.get_json()['data']}"}

    # User 1 hides the cell above; user 2 hides it below
    client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [cell_id], "hidden_below": []},
        headers=auth_headers,
    )
    client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [], "hidden_below": [cell_id]},
        headers=headers2,
    )

    resp1 = client.get(f"/family_trees/{family_tree_id}/hidden_branches", headers=auth_headers)
    resp2 = client.get(f"/family_trees/{family_tree_id}/hidden_branches", headers=headers2)

    assert resp1.get_json()["data"] == {"hidden_above": [cell_id], "hidden_below": []}
    assert resp2.get_json()["data"] == {"hidden_above": [], "hidden_below": [cell_id]}


def test_put_hidden_branches_forbidden_for_viewer(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    cell_id: int,
) -> None:
    """A viewer cannot hide/show branches, but can still read the state."""
    client.post("/user", json={
        "name": "Viewer", "surname": "User",
        "email": "viewer_hb@test.com", "password": "pw3",
    })
    from app.models import User
    viewer = User.query.filter_by(email="viewer_hb@test.com").first()
    viewer.verified = True
    _db.session.commit()
    _db.session.execute(
        insert(association_user_ft).values(
            id_user=viewer.id_user,
            id_family_tree=family_tree_id,
            role="viewer",
        )
    )
    _db.session.commit()
    login = client.post("/login", json={"email": "viewer_hb@test.com", "password": "pw3"})
    viewer_headers = {"Authorization": f"Bearer {login.get_json()['data']}"}

    put_response = client.put(
        f"/family_trees/{family_tree_id}/hidden_branches",
        json={"hidden_above": [cell_id], "hidden_below": []},
        headers=viewer_headers,
    )
    assert put_response.status_code == 403

    get_response = client.get(
        f"/family_trees/{family_tree_id}/hidden_branches",
        headers=viewer_headers,
    )
    assert get_response.status_code == 200
    assert get_response.get_json()["data"] == {"hidden_above": [], "hidden_below": []}
