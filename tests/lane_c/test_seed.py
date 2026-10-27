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
