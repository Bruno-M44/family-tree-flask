from typing import Optional
from urllib.parse import quote

import pytest
from flask.testing import FlaskClient

from app import db as _db
from app.models import User, association_user_ft

from .conftest import USER_1

USER_2: dict = {
    "name": "Martin",
    "surname": "Claire",
    "email": "claire.martin@test.com",
    "password": "password2",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def family_tree_id(client: FlaskClient, auth_headers: dict) -> int:
    """Create a family tree for USER_1 and return its ID."""
    response = client.post(
        "/family_tree",
        json={"title": "Test Tree", "family_name": "Test"},
        headers=auth_headers,
    )
    return response.get_json()["data"]["id_family_tree"]


@pytest.fixture
def second_user(client: FlaskClient) -> User:
    """Create USER_2 in the database and mark them as verified."""
    client.post("/user", json=USER_2)
    user: User = User.query.filter_by(email=USER_2["email"]).first()
    user.verified = True
    _db.session.commit()
    return user


@pytest.fixture
def second_user_as_member(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> User:
    """Add USER_2 as a viewer member of USER_1's family tree."""
    client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "viewer"},
        headers=auth_headers,
    )
    return second_user


@pytest.fixture
def viewer_headers(client: FlaskClient, second_user: User) -> dict:
    """Return JWT auth headers for USER_2, who has viewer role."""
    response = client.post("/login", json=USER_2)
    token: str = response.get_json()["data"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /user/family-tree/<id>/members
# ---------------------------------------------------------------------------

def test_get_members_includes_current_user(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """The members list includes the authenticated user."""
    response = client.get(f"/user/family-tree/{family_tree_id}/members", headers=auth_headers)
    assert response.status_code == 200
    members: list = response.get_json()["data"]
    emails: list = [m["email"] for m in members]
    assert USER_1["email"] in emails


def test_get_members_includes_added_member(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """The members list includes a newly added member with their role."""
    response = client.get(f"/user/family-tree/{family_tree_id}/members", headers=auth_headers)
    assert response.status_code == 200
    members: list = response.get_json()["data"]
    match = next((m for m in members if m["email"] == USER_2["email"]), None)
    assert match is not None
    assert match["role"] == "viewer"
    assert "id_user" in match
    assert "name" in match
    assert "surname" in match


def test_get_members_forbidden_for_non_member(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """A user who is not a member of the tree gets 403."""
    response = client.get(f"/user/family-tree/{family_tree_id}/members", headers=viewer_headers)
    assert response.status_code == 403


def test_get_members_unauthenticated(
    client: FlaskClient,
    family_tree_id: int,
) -> None:
    """An unauthenticated request returns 401."""
    response = client.get(f"/user/family-tree/{family_tree_id}/members")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /user/family-tree/<id>/member
# ---------------------------------------------------------------------------

def test_add_member_ok_viewer(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """An editor can add a user as viewer."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.get_json()["message"] == "Member added"


def test_add_member_ok_editor(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """An editor can add a user as editor."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "editor"},
        headers=auth_headers,
    )
    assert response.status_code == 201


def test_add_member_default_role_is_viewer(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """When role is omitted, the new member is assigned viewer by default."""
    client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"]},
        headers=auth_headers,
    )
    row = _db.session.execute(
        association_user_ft.select().where(
            association_user_ft.c.id_user == second_user.id_user,
            association_user_ft.c.id_family_tree == family_tree_id,
        )
    ).first()
    assert row.role == "viewer"


def test_add_member_missing_email(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """Request without email field returns 400."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Missing email"


def test_add_member_invalid_role(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """An unrecognised role value returns 400."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "superadmin"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_add_member_unknown_email_sends_invitation(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """Adding an unknown email creates a pending invitation and returns status invitation_sent."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": "nobody@unknown.com", "role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "invitation_sent"


def test_register_consumes_pending_invitation(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """A new user who registers with an invited email is automatically added to the tree."""
    invited_email: str = "invited@example.com"
    client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": invited_email, "role": "viewer"},
        headers=auth_headers,
    )
    client.post("/user", json={
        "name": "Invited",
        "surname": "User",
        "email": invited_email,
        "password": "password123",
    })
    new_user = User.query.filter_by(email=invited_email).first()
    assert new_user is not None
    row = _db.session.execute(
        association_user_ft.select().where(
            association_user_ft.c.id_user == new_user.id_user,
            association_user_ft.c.id_family_tree == family_tree_id,
        )
    ).first()
    assert row is not None
    assert row.role == "viewer"


def test_add_member_already_member(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """Adding a user who is already a member returns 409."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.get_json()["message"] == "User already member of this tree"


def test_add_member_forbidden_for_viewer(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """A viewer cannot add members to the tree."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_1["email"], "role": "viewer"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_add_member_unauthenticated(
    client: FlaskClient,
    family_tree_id: int,
) -> None:
    """An unauthenticated request returns 401."""
    response = client.post(
        f"/user/family-tree/{family_tree_id}/member",
        json={"email": USER_2["email"], "role": "viewer"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /user/family-tree/<id>/leave
# ---------------------------------------------------------------------------

def test_leave_family_tree_ok(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """A member (viewer) can leave a family tree they belong to."""
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/leave",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "You have left the tree"


def test_leave_family_tree_last_member_blocked(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """The sole remaining member cannot leave the tree."""
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/leave",
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_leave_family_tree_last_editor_blocked(
    client: FlaskClient,
    auth_headers: dict,
    viewer_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """The last editor cannot leave even if there are other viewers."""
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/leave",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "last editor" in response.get_json()["message"]


def test_leave_family_tree_not_member(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """A user who is not a member of the tree gets 404."""
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/leave",
        headers=viewer_headers,
    )
    assert response.status_code == 404


def test_leave_family_tree_unauthenticated(
    client: FlaskClient,
    family_tree_id: int,
) -> None:
    """An unauthenticated request returns 401."""
    response = client.delete(f"/user/family-tree/{family_tree_id}/leave")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /user/family-tree/<id>/member/<email>
# ---------------------------------------------------------------------------

def test_remove_member_ok(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An editor can remove an existing member."""
    email: str = quote(USER_2["email"], safe="")
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Member removed"


def test_remove_member_user_not_found(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """Removing a non-existent email returns 404."""
    email: str = quote("nobody@unknown.com", safe="")
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.get_json()["message"] == "User not found"


def test_remove_member_not_member_of_tree(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """Removing a user who is not a member of the tree returns 404."""
    email: str = quote(USER_2["email"], safe="")
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.get_json()["message"] == "User not member of this tree"


def test_remove_member_last_member_blocked(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """Removing the sole remaining member of a tree returns 409."""
    email: str = quote(USER_1["email"], safe="")
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.get_json()["message"] == "Cannot remove the last member of a tree"


def test_remove_member_forbidden_for_viewer(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """A viewer cannot remove members from the tree."""
    email: str = quote(USER_2["email"], safe="")
    response = client.delete(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_remove_member_unauthenticated(
    client: FlaskClient,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An unauthenticated request returns 401."""
    email: str = quote(USER_2["email"], safe="")
    response = client.delete(f"/user/family-tree/{family_tree_id}/member/{email}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /user/family-tree/<id>/member/<email>
# ---------------------------------------------------------------------------

def test_update_member_role_to_editor(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An editor can promote a viewer to editor."""
    email: str = quote(USER_2["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "editor"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Role updated"


def test_update_member_role_to_viewer(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An editor can demote another editor to viewer."""
    email: str = quote(USER_2["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_update_member_role_invalid_role(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An unrecognised role value returns 400."""
    email: str = quote(USER_2["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "superadmin"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_update_member_role_user_not_found(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
) -> None:
    """Updating the role of a non-existent email returns 404."""
    email: str = quote("nobody@unknown.com", safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "editor"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.get_json()["message"] == "User not found"


def test_update_member_role_not_member_of_tree(
    client: FlaskClient,
    auth_headers: dict,
    family_tree_id: int,
    second_user: User,
) -> None:
    """Updating the role of a user who is not a member returns 404."""
    email: str = quote(USER_2["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "editor"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.get_json()["message"] == "User not member of this tree"


def test_update_member_role_forbidden_for_viewer(
    client: FlaskClient,
    viewer_headers: dict,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """A viewer cannot update member roles."""
    email: str = quote(USER_1["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "viewer"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_update_member_role_unauthenticated(
    client: FlaskClient,
    family_tree_id: int,
    second_user_as_member: User,
) -> None:
    """An unauthenticated request returns 401."""
    email: str = quote(USER_2["email"], safe="")
    response = client.patch(
        f"/user/family-tree/{family_tree_id}/member/{email}",
        json={"role": "editor"},
    )
    assert response.status_code == 401
