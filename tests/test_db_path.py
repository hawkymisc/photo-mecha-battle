from pathlib import Path

from photo_mecha_battle.api.database import Database
from photo_mecha_battle.api.db_path import resolve_db_path


def test_resolve_db_path_defaults_under_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("PMB_DB_PATH", raising=False)
    monkeypatch.setenv("PMB_DATA_DIR", str(tmp_path / "data"))
    path = resolve_db_path()
    assert path == tmp_path / "data" / "pmb.sqlite3"


def test_resolve_db_path_honors_explicit_override(tmp_path, monkeypatch):
    explicit = tmp_path / "custom" / "game.db"
    monkeypatch.setenv("PMB_DB_PATH", str(explicit))
    monkeypatch.setenv("PMB_DATA_DIR", str(tmp_path / "ignored"))
    assert resolve_db_path() == explicit


def test_file_database_survives_reopen(tmp_path):
    db_file = tmp_path / "pmb.sqlite3"
    db = Database(str(db_file))
    user = db.create_user("FilePersist")
    db.update_rating(user.id, 25)
    db.close()

    reopened = Database(str(db_file))
    ranking = reopened.get_ranking()
    assert ranking[0]["team_name"] == "FilePersist"
    assert ranking[0]["rating"] == 1025
    reopened.close()


def test_resolve_db_path_creates_parent_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "dir" / "pmb.sqlite3"
    monkeypatch.setenv("PMB_DB_PATH", str(target))
    path = resolve_db_path(ensure_parent=True)
    assert path == target
    assert path.parent.is_dir()
