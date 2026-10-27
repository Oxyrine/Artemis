from sqlalchemy import create_engine, text

from scripts import seed


def test_seed_migrates_loads_once_and_creates_the_key(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    key = tmp_path / "keys" / "signing_key.pem"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SIGNING_KEY_PATH", str(key))

    first = seed.seed(url)
    assert first["cases"] == 40 and first["reviewers"] == 2 and key.exists()

    key_bytes = key.read_bytes()
    with create_engine(url).connect() as c:
        events = c.execute(text("SELECT count(*) FROM audit_events")).scalar()
        version = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "0001" and events > 0

    again = seed.seed(url)  # a restart must neither reload nor wipe anything
    assert again["cases"] == 40 and key.read_bytes() == key_bytes
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT count(*) FROM audit_events")).scalar() == events


def test_host_style_database_urls_get_the_psycopg_driver():
    from artemis.db import normalize_url
    assert normalize_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///x.db") == "sqlite:///x.db"
