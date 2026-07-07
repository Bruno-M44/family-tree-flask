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
