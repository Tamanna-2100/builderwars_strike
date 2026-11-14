import pytest

from app import app
from seed import seed


@pytest.fixture
def client(tmp_path):
    database = str(tmp_path / "notes.db")
    seed(database)
    app.config.update(TESTING=True, DATABASE=database)
    with app.test_client() as client:
        yield client


def test_get_note(client):
    response = client.get("/notes/1", headers={"X-Token": "alice-token"})
    assert response.status_code == 200
    assert response.json["body"] == "Alice's example note"


def test_search(client):
    response = client.get("/search?q=secret", headers={"X-Token": "bob-token"})
    assert response.status_code == 200
    assert [note["body"] for note in response.json] == ["BOB_SECRET_123"]


def test_list_users(client):
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert response.json == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]


def test_notes_require_authentication(client):
    assert client.get("/notes/1").status_code == 401
    assert client.get("/search?q=note").status_code == 401