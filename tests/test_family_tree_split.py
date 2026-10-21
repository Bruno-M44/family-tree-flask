import io
import os

from flask.testing import FlaskClient
from sqlalchemy import select

from app import db as _db
from app.models import FamilyTree, FamilyTreeCell, FamilyTreeHiddenBranches, User, association_user_ft

from .test_member_management import (  # noqa: F401
    USER_2, family_tree_id, second_user, second_user_as_member, viewer_headers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_tree(client: FlaskClient, headers: dict, title: str, family_name: str) -> int:
    response = client.post(
        "/family_tree", json={"title": title, "family_name": family_name}, headers=headers
    )
    return response.get_json()["data"]["id_family_tree"]


def _create_cell(client: FlaskClient, headers: dict, id_family_tree: int, **kwargs) -> int:
    body = {"name": "Doe", "surnames": "John", "generation": 0, **kwargs}
    response = client.post(
        f"/family_trees/{id_family_tree}/family_tree_cells", json=body, headers=headers
    )
    return response.get_json()["data"]["id_family_tree_cell"]


def _create_couple(client: FlaskClient, headers: dict, id_family_tree: int, id_cell: int, id_partner: int) -> None:
    response = client.post(
        f"/family_trees/{id_family_tree}/family_tree_cells/{id_cell}/couple",
        json={"partner_id": id_partner},
        headers=headers,
    )
    assert response.status_code in (200, 201)


# ---------------------------------------------------------------------------
# POST /family_trees/<id_family_tree>/split
# ---------------------------------------------------------------------------

def test_split_unauthenticated(client: FlaskClient) -> None:
    response = client.post("/family_trees/1/split", json={"id_cell_root": 1, "title": "B", "family_name": "B"})
    assert response.status_code == 401


def test_split_missing_fields(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    response = client.post(f"/family_trees/{tree_a}/split", json={}, headers=auth_headers)
    assert response.status_code == 400


def test_split_forbidden_for_viewer(
    client: FlaskClient,
    viewer_headers: dict,  # noqa: F811
    family_tree_id: int,  # noqa: F811
    second_user_as_member: User,  # noqa: F811
) -> None:
    """USER_2 is only viewer on the tree (via second_user_as_member)."""
    response = client.post(
        f"/family_trees/{family_tree_id}/split",
        json={"id_cell_root": 1, "title": "B", "family_name": "B"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_split_tree_not_found(client: FlaskClient, auth_headers: dict) -> None:
    response = client.post(
        "/family_trees/999999/split",
        json={"id_cell_root": 1, "title": "B", "family_name": "B"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_split_cell_not_found(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": 999999, "title": "B", "family_name": "B"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_split_demo_tree_rejected(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    cell = _create_cell(client, auth_headers, tree_a)
    tree = _db.session.get(FamilyTree, tree_a)
    tree.is_example = True
    _db.session.commit()

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": cell, "title": "B", "family_name": "B"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_split_ok_nominal(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    root = _create_cell(client, auth_headers, tree_a, generation=4)
    child = _create_cell(client, auth_headers, tree_a, generation=5, parents=[root])

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    tree_b = response.get_json()["data"]["id_family_tree"]
    assert tree_b != tree_a

    root_cell = _db.session.get(FamilyTreeCell, root)
    child_cell = _db.session.get(FamilyTreeCell, child)
    assert root_cell.id_family_tree == tree_b
    assert child_cell.id_family_tree == tree_b
    # Root's generation realigned to 0, child keeps its relative offset (+1).
    assert root_cell.generation == 0
    assert child_cell.generation == 1


def test_split_excludes_ancestors_and_siblings(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    parent = _create_cell(client, auth_headers, tree_a, generation=0)
    root = _create_cell(client, auth_headers, tree_a, generation=1, parents=[parent])
    sibling = _create_cell(client, auth_headers, tree_a, generation=1, parents=[parent])
    grandchild = _create_cell(client, auth_headers, tree_a, generation=2, parents=[root])

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    tree_b = response.get_json()["data"]["id_family_tree"]

    assert _db.session.get(FamilyTreeCell, parent).id_family_tree == tree_a
    assert _db.session.get(FamilyTreeCell, sibling).id_family_tree == tree_a
    assert _db.session.get(FamilyTreeCell, root).id_family_tree == tree_b
    assert _db.session.get(FamilyTreeCell, grandchild).id_family_tree == tree_b


def test_split_moves_spouse_of_descendant(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    root = _create_cell(client, auth_headers, tree_a, generation=0)
    child = _create_cell(client, auth_headers, tree_a, generation=1, parents=[root])
    spouse = _create_cell(client, auth_headers, tree_a, generation=1)
    _create_couple(client, auth_headers, tree_a, child, spouse)

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    tree_b = response.get_json()["data"]["id_family_tree"]
    assert _db.session.get(FamilyTreeCell, spouse).id_family_tree == tree_b


def test_split_rejects_blended_family_conflict(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    root = _create_cell(client, auth_headers, tree_a, generation=0)
    descendant = _create_cell(client, auth_headers, tree_a, generation=1, parents=[root])
    outsider = _create_cell(client, auth_headers, tree_a, generation=1)
    # A child shared between `descendant` (in the would-be subtree) and
    # `outsider` (unrelated, stays behind) — this must block the split.
    _create_cell(client, auth_headers, tree_a, generation=2, parents=[descendant, outsider])

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    conflicts = response.get_json()["data"]["conflicts"]
    assert any(c["outside"] == outsider for c in conflicts)

    # Nothing was mutated: root is still in tree_a.
    assert _db.session.get(FamilyTreeCell, root).id_family_tree == tree_a


def test_split_drops_moved_cells_from_hidden_branches(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    stays = _create_cell(client, auth_headers, tree_a, generation=0)
    root = _create_cell(client, auth_headers, tree_a, generation=0)

    client.put(
        f"/family_trees/{tree_a}/hidden_branches",
        json={"hidden_above": [stays, root], "hidden_below": []},
        headers=auth_headers,
    )

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 201

    row = FamilyTreeHiddenBranches.query.filter_by(id_family_tree=tree_a).first()
    assert row.hidden_above == [stays]


def test_split_copies_memberships_to_new_tree(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,  # noqa: F811
    second_user_as_member: User,  # noqa: F811
) -> None:
    """USER_2 is viewer on the source tree; must remain viewer on the new one too."""
    tree_a = family_tree_id
    root = _create_cell(client, auth_headers, tree_a, generation=0)

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    tree_b = response.get_json()["data"]["id_family_tree"]

    user_2 = User.query.filter_by(email=USER_2["email"]).first()
    role = _db.session.execute(
        select(association_user_ft.c.role).where(
            association_user_ft.c.id_user == user_2.id_user,
            association_user_ft.c.id_family_tree == tree_b,
        )
    ).scalar_one()
    assert role == "viewer"


def test_split_moves_pictures_to_new_tree_folder(app, client: FlaskClient, auth_headers: dict) -> None:
    pictures_root = app.config['PICTURES_ROOT']
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    root = _create_cell(client, auth_headers, tree_a, generation=0)

    client.post(
        f"/family_trees/{tree_a}/family_tree_cells/{root}/pictures",
        data={"file": (io.BytesIO(b"fake image"), "photo.jpg"), "header_picture": "true"},
        headers=auth_headers,
        content_type="multipart/form-data",
    )
    assert os.path.isdir(f"{pictures_root}/{tree_a}/{root}")

    response = client.post(
        f"/family_trees/{tree_a}/split",
        json={"id_cell_root": root, "title": "B", "family_name": "Fam B"},
        headers=auth_headers,
    )
    tree_b = response.get_json()["data"]["id_family_tree"]

    assert not os.path.isdir(f"{pictures_root}/{tree_a}/{root}")
    assert os.path.isdir(f"{pictures_root}/{tree_b}/{root}")
