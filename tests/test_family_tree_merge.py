import io
import os

from flask.testing import FlaskClient
from sqlalchemy import select

from app import db as _db
from app.models import (
    FamilyTree, FamilyTreeCell, FamilyTreeHiddenBranches, User, association_couple, association_parent_child,
    association_user_ft,
)

from .conftest import USER_1
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


# ---------------------------------------------------------------------------
# POST /family_trees/<id_family_tree_a>/merge
# ---------------------------------------------------------------------------

def test_merge_unauthenticated(client: FlaskClient) -> None:
    response = client.post("/family_trees/1/merge", json={"id_family_tree_b": 2, "id_cell_a": 1, "id_cell_b": 2})
    assert response.status_code == 401


def test_merge_missing_fields(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    response = client.post(f"/family_trees/{tree_a}/merge", json={}, headers=auth_headers)
    assert response.status_code == 400


def test_merge_self_rejected(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    cell_a = _create_cell(client, auth_headers, tree_a)
    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_a, "id_cell_a": cell_a, "id_cell_b": cell_a},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_merge_forbidden_for_viewer_on_other_tree(
    client: FlaskClient,
    auth_headers: dict,
    viewer_headers: dict,  # noqa: F811
    family_tree_id: int,  # noqa: F811
    second_user_as_member: User,  # noqa: F811
) -> None:
    """USER_2 is only viewer on tree A (via second_user_as_member); they own tree B
    themselves but must be editor of BOTH trees to merge."""
    tree_a = family_tree_id
    tree_b = _create_tree(client, viewer_headers, "B", "Fam B")
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_b = _create_cell(client, viewer_headers, tree_b)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_b},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_merge_not_found(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    cell_a = _create_cell(client, auth_headers, tree_a)
    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": 999999, "id_cell_a": cell_a, "id_cell_b": 1},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_merge_cell_not_in_expected_tree(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_a_2 = _create_cell(client, auth_headers, tree_a)  # also in tree A, not B

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_a_2},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_merge_ok_same_owner(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "Smith", "Smith")
    tree_b = _create_tree(client, auth_headers, "Doe", "Doe")

    husband = _create_cell(client, auth_headers, tree_a, name="Smith", surnames="John", generation=0)
    child_a = _create_cell(
        client, auth_headers, tree_a, name="Smith", surnames="Junior", generation=1,
        parents=[husband],
    )
    wife = _create_cell(client, auth_headers, tree_b, name="Doe", surnames="Jane", generation=3)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={
            "id_family_tree_b": tree_b,
            "id_cell_a": husband,
            "id_cell_b": wife,
            "start_union": "01/06/2010",
            "type_union": "mariage",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["id_family_tree"] == tree_a

    # Tree B no longer exists.
    assert _db.session.get(FamilyTree, tree_b) is None

    # Wife's cell reassigned to A.
    wife_cell = _db.session.get(FamilyTreeCell, wife)
    assert wife_cell.id_family_tree == tree_a
    # Wife's generation realigned onto the husband's (0), was 3 before merge.
    assert wife_cell.generation == 0
    # Descendant of the untouched tree A cell keeps its own generation.
    assert _db.session.get(FamilyTreeCell, child_a).generation == 1

    # Couple relation created between the join-point cells.
    couple_row = _db.session.execute(
        select(association_couple).where(
            association_couple.c.id_family_tree_cell_couple_1 == husband,
            association_couple.c.id_family_tree_cell_couple_2 == wife,
        )
    ).first()
    assert couple_row is not None
    assert couple_row.type_union == "mariage"


def test_merge_realigns_generations_of_whole_subtree(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")

    cell_a = _create_cell(client, auth_headers, tree_a, generation=0)
    wife = _create_cell(client, auth_headers, tree_b, generation=5)
    wife_child = _create_cell(client, auth_headers, tree_b, generation=6, parents=[wife])

    client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": wife},
        headers=auth_headers,
    )

    # offset = 0 - 5 = -5, applied to every cell that was in tree B.
    assert _db.session.get(FamilyTreeCell, wife).generation == 0
    assert _db.session.get(FamilyTreeCell, wife_child).generation == 1


def test_merge_merges_memberships_editor_wins(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,  # noqa: F811
    second_user_as_member: User,  # noqa: F811
) -> None:
    """USER_2 is viewer on tree A and editor on tree B (their own tree):
    after merge they must end up editor on the merged tree."""
    tree_a = family_tree_id
    user_2_headers: dict = {
        "Authorization": f"Bearer {client.post('/login', json=USER_2).get_json()['data']}"
    }
    tree_b = _create_tree(client, user_2_headers, "B", "Fam B")
    # USER_1 (who performs the merge) must also be editor of tree B beforehand
    # (mirrors the real flow: both partners share their tree with each other first).
    client.post(
        f"/user/family-tree/{tree_b}/member",
        json={"email": USER_1["email"], "role": "editor"},
        headers=user_2_headers,
    )
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_b = _create_cell(client, user_2_headers, tree_b)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_b},
        headers=auth_headers,
    )
    assert response.status_code == 200

    user_2 = User.query.filter_by(email=USER_2["email"]).first()
    role = _db.session.execute(
        select(association_user_ft.c.role).where(
            association_user_ft.c.id_user == user_2.id_user,
            association_user_ft.c.id_family_tree == tree_a,
        )
    ).scalar_one()
    assert role == "editor"


def test_merge_drops_hidden_branches_of_tree_b(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_b = _create_cell(client, auth_headers, tree_b)

    client.put(
        f"/family_trees/{tree_b}/hidden_branches",
        json={"hidden_above": [cell_b], "hidden_below": []},
        headers=auth_headers,
    )
    assert FamilyTreeHiddenBranches.query.filter_by(id_family_tree=tree_b).first() is not None

    client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_b},
        headers=auth_headers,
    )
    assert FamilyTreeHiddenBranches.query.filter_by(id_family_tree=tree_b).first() is None


def test_merge_moves_pictures_to_target_tree_folder(app, client: FlaskClient, auth_headers: dict) -> None:
    pictures_root = app.config['PICTURES_ROOT']
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_b = _create_cell(client, auth_headers, tree_b)

    client.post(
        f"/family_trees/{tree_b}/family_tree_cells/{cell_b}/pictures",
        data={"file": (io.BytesIO(b"fake image"), "photo.jpg"), "header_picture": "true"},
        headers=auth_headers,
        content_type="multipart/form-data",
    )
    assert os.path.isdir(f"{pictures_root}/{tree_b}/{cell_b}")

    client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_b},
        headers=auth_headers,
    )

    assert not os.path.isdir(f"{pictures_root}/{tree_b}/{cell_b}")
    assert os.path.isdir(f"{pictures_root}/{tree_a}/{cell_b}")


# ---------------------------------------------------------------------------
# link_type: child_of / parent_of (ex. refusionner un arbre issu d'une scission)
# ---------------------------------------------------------------------------

def _create_couple(client: FlaskClient, headers: dict, id_family_tree: int, id_cell: int, id_partner: int) -> None:
    response = client.post(
        f"/family_trees/{id_family_tree}/family_tree_cells/{id_cell}/couple",
        json={"partner_id": id_partner},
        headers=headers,
    )
    assert response.status_code in (200, 201)


def _parent_ids_of(id_child: int) -> set:
    return {
        row.id_family_tree_cell_parent
        for row in _db.session.execute(
            select(association_parent_child).where(
                association_parent_child.c.id_family_tree_cell_child == id_child
            )
        )
    }


def test_merge_child_of_links_both_parents_and_realigns(client: FlaskClient, auth_headers: dict) -> None:
    """Cas « refusion d'une scission » : Margaret (racine de A) redevient l'enfant de
    George VI × Élisabeth (dans B)."""
    tree_a = _create_tree(client, auth_headers, "Famille de Margaret", "Windsor")
    tree_b = _create_tree(client, auth_headers, "Maison de Windsor", "Windsor")
    margaret = _create_cell(client, auth_headers, tree_a, generation=0)
    margaret_child = _create_cell(client, auth_headers, tree_a, generation=1, parents=[margaret])
    george = _create_cell(client, auth_headers, tree_b, generation=3)
    elizabeth = _create_cell(client, auth_headers, tree_b, generation=3)
    _create_couple(client, auth_headers, tree_b, george, elizabeth)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={
            "id_family_tree_b": tree_b, "id_cell_a": margaret, "id_cell_b": george,
            "link_type": "child_of", "id_second_parent": elizabeth,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    assert _parent_ids_of(margaret) == {george, elizabeth}
    # Les parents passent une génération au-dessus de Margaret ; A ne bouge pas.
    assert _db.session.get(FamilyTreeCell, george).generation == -1
    assert _db.session.get(FamilyTreeCell, elizabeth).generation == -1
    assert _db.session.get(FamilyTreeCell, margaret).generation == 0
    assert _db.session.get(FamilyTreeCell, margaret_child).generation == 1
    assert _db.session.get(FamilyTreeCell, george).id_family_tree == tree_a
    assert _db.session.get(FamilyTree, tree_b) is None
    # Aucun couple créé pour un lien parent/enfant.
    assert _db.session.execute(
        select(association_couple).where(association_couple.c.id_family_tree_cell_couple_1 == margaret)
    ).first() is None


def test_merge_parent_of_without_second_parent(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    parent = _create_cell(client, auth_headers, tree_a, generation=2)
    child = _create_cell(client, auth_headers, tree_b, generation=7)
    grandchild = _create_cell(client, auth_headers, tree_b, generation=8, parents=[child])

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": parent, "id_cell_b": child, "link_type": "parent_of"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    assert _parent_ids_of(child) == {parent}
    assert _db.session.get(FamilyTreeCell, child).generation == 3
    assert _db.session.get(FamilyTreeCell, grandchild).generation == 4


def test_merge_child_of_rejected_if_child_already_has_parents(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    existing_parent = _create_cell(client, auth_headers, tree_a, generation=0)
    child = _create_cell(client, auth_headers, tree_a, generation=1, parents=[existing_parent])
    other_parent = _create_cell(client, auth_headers, tree_b, generation=0)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={"id_family_tree_b": tree_b, "id_cell_a": child, "id_cell_b": other_parent, "link_type": "child_of"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    # Rien n'a bougé.
    assert _db.session.get(FamilyTree, tree_b) is not None
    assert _parent_ids_of(child) == {existing_parent}


def test_merge_second_parent_must_be_spouse_of_parent(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    child = _create_cell(client, auth_headers, tree_a, generation=0)
    parent = _create_cell(client, auth_headers, tree_b, generation=0)
    stranger = _create_cell(client, auth_headers, tree_b, generation=0)

    response = client.post(
        f"/family_trees/{tree_a}/merge",
        json={
            "id_family_tree_b": tree_b, "id_cell_a": child, "id_cell_b": parent,
            "link_type": "child_of", "id_second_parent": stranger,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert _db.session.get(FamilyTree, tree_b) is not None


def test_merge_invalid_link_type(client: FlaskClient, auth_headers: dict) -> None:
    tree_a = _create_tree(client, auth_headers, "A", "Fam A")
    tree_b = _create_tree(client, auth_headers, "B", "Fam B")
    cell_a = _create_cell(client, auth_headers, tree_a)
    cell_b = _create_cell(client, auth_headers, tree_b)

    for body_extra in ({"link_type": "sibling_of"}, {"link_type": "couple", "id_second_parent": cell_b}):
        response = client.post(
            f"/family_trees/{tree_a}/merge",
            json={"id_family_tree_b": tree_b, "id_cell_a": cell_a, "id_cell_b": cell_b, **body_extra},
            headers=auth_headers,
        )
        assert response.status_code == 400
