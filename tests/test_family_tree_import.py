import io
import json
import zipfile
from unittest.mock import patch


def _build_import_zip(tree_json: dict) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('tree.json', json.dumps(tree_json))
    buf.seek(0)
    return buf


def test_import_family_tree_rejects_archive_too_large_uncompressed(client, auth_headers):
    """Guards against zip bombs: total uncompressed size is capped regardless
    of how small the compressed upload is."""
    tree_json = {'title': 'T', 'family_name': 'F', 'cells': [], 'relations': {'parent_child': [], 'couples': []}}
    zip_buf = _build_import_zip(tree_json)

    with patch('app.views.family_tree_view.MAX_IMPORT_UNCOMPRESSED_SIZE', 10):
        response = client.post(
            '/family_trees/import',
            data={'file': (zip_buf, 'tree.zip')},
            headers=auth_headers,
            content_type='multipart/form-data',
        )
    assert response.status_code == 400
    assert 'too large' in response.get_json()['message'].lower()


def test_import_family_tree_accepts_small_archive(client, auth_headers):
    tree_json = {'title': 'Imported', 'family_name': 'Fam', 'cells': [], 'relations': {'parent_child': [], 'couples': []}}
    zip_buf = _build_import_zip(tree_json)

    response = client.post(
        '/family_trees/import',
        data={'file': (zip_buf, 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 201


def test_import_family_tree_no_file(client, auth_headers):
    response = client.post('/family_trees/import', headers=auth_headers, content_type='multipart/form-data')
    assert response.status_code == 400
    assert 'No file provided' in response.get_json()['message']


def test_import_family_tree_unauthenticated(client):
    zip_buf = _build_import_zip({'title': 'T', 'family_name': 'F', 'cells': [], 'relations': {'parent_child': [], 'couples': []}})
    response = client.post(
        '/family_trees/import', data={'file': (zip_buf, 'tree.zip')}, content_type='multipart/form-data',
    )
    assert response.status_code == 401


def test_import_family_tree_rejects_non_zip_extension(client, auth_headers):
    response = client.post(
        '/family_trees/import',
        data={'file': (io.BytesIO(b'not a zip'), 'tree.txt')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'ZIP archive' in response.get_json()['message']


def test_import_family_tree_rejects_invalid_zip(client, auth_headers):
    response = client.post(
        '/family_trees/import',
        data={'file': (io.BytesIO(b'this is not a real zip file'), 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'Invalid ZIP' in response.get_json()['message']


def test_import_family_tree_rejects_missing_tree_json(client, auth_headers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('other.json', '{}')
    buf.seek(0)
    response = client.post(
        '/family_trees/import',
        data={'file': (buf, 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'missing tree.json' in response.get_json()['message']


def test_import_family_tree_rejects_missing_required_field(client, auth_headers):
    zip_buf = _build_import_zip({'title': 'T', 'cells': [], 'relations': {'parent_child': [], 'couples': []}})
    response = client.post(
        '/family_trees/import',
        data={'file': (zip_buf, 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'family_name' in response.get_json()['message']


def test_import_family_tree_rejects_malformed_json(client, auth_headers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('tree.json', 'not valid json{{{')
    buf.seek(0)
    response = client.post(
        '/family_trees/import',
        data={'file': (buf, 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'Invalid tree.json format' in response.get_json()['message']


def test_import_family_tree_creates_cells_with_relations(client, auth_headers):
    tree_json = {
        'title': 'Full Import',
        'family_name': 'Fam',
        'cells': [
            {'export_id': 1, 'name': 'Dupont', 'surnames': 'Alice', 'generation': 0},
            {'export_id': 2, 'name': 'Martin', 'surnames': 'Bruno', 'generation': 0},
            {'export_id': 3, 'name': 'Dupont', 'surnames': 'Celeste', 'generation': 1},
        ],
        'relations': {
            'parent_child': [
                {'parent_id': 1, 'child_id': 3},
                {'parent_id': 2, 'child_id': 3},
            ],
            'couples': [
                {'cell_1_id': 1, 'cell_2_id': 2, 'start_union': '01/06/2000', 'end_union': None},
            ],
        },
    }
    zip_buf = _build_import_zip(tree_json)
    response = client.post(
        '/family_trees/import',
        data={'file': (zip_buf, 'tree.zip')},
        headers=auth_headers,
        content_type='multipart/form-data',
    )
    assert response.status_code == 201

    trees = client.get('/family_trees', headers=auth_headers).get_json()['data']
    imported = next(t for t in trees if t['title'] == 'Full Import')
    cells = client.get(
        f"/family_trees/{imported['id_family_tree']}/family_tree_cells", headers=auth_headers,
    ).get_json()['data']
    assert len(cells) == 3
    celeste = next(c for c in cells if c['surnames'] == 'Celeste')
    assert len(celeste['children']) == 0
    assert celeste['orphan'] is False
    alice = next(c for c in cells if c['surnames'] == 'Alice')
    assert any(c['surnames'] == 'Bruno' for c in alice['couples'])
    assert any(c['surnames'] == 'Celeste' for c in alice['children'])
