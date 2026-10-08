"""Account deletion removes the learner's stored artwork (WP-138).

The relational rows cascade with the user; the panel images live outside the
database (S3 or the local image directory) and are removed best effort.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect as sa_inspect

from app.config import settings
from app.db.base import Base
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.services.graphic_novel_image_storage import GraphicNovelImageStorage
from app.services.users import UserService


@pytest.fixture()
def deletable(db_session):
    """The shared test schema omits some tables the User mapper cascades into;
    create the missing ones so the ORM delete runs, and drop them afterwards."""

    bind = db_session.get_bind()
    present = set(sa_inspect(bind).get_table_names())
    wanted = {rel.mapper.local_table for rel in sa_inspect(User).relationships}
    missing = [table for table in wanted if table.name not in present]
    Base.metadata.create_all(bind=bind, tables=missing)
    try:
        yield db_session
    finally:
        db_session.rollback()
        Base.metadata.drop_all(bind=bind, tables=missing)


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"artwork-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _scene(db_session, user: User) -> GraphicNovelScene:
    scene = GraphicNovelScene(
        id=uuid4(),
        user_id=user.id,
        title="Scène",
        brief="brief",
        cache_key=f"key-{uuid4()}",
        prompt_version="test",
        image_model="test",
        image_quality="low",
    )
    db_session.add(scene)
    db_session.commit()
    return scene


class FakeStorage:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list] = []
        self.fail = fail

    def delete_scene_objects(self, scene_ids):
        self.calls.append(list(scene_ids))
        if self.fail:
            raise RuntimeError("bucket unreachable")
        return len(self.calls[-1])


def test_deletion_hands_every_scene_of_the_learner_to_the_store(deletable) -> None:
    db_session = deletable
    user = _user(db_session)
    other = _user(db_session)
    mine = {_scene(db_session, user).id, _scene(db_session, user).id}
    _scene(db_session, other)
    user_id = user.id

    storage = FakeStorage()
    UserService(db_session, image_storage=storage).delete(user)

    assert db_session.get(User, user_id) is None
    assert len(storage.calls) == 1
    assert set(storage.calls[0]) == mine


def test_a_failing_store_never_blocks_the_deletion(deletable) -> None:
    db_session = deletable
    user = _user(db_session)
    _scene(db_session, user)
    user_id = user.id

    storage = FakeStorage(fail=True)
    UserService(db_session, image_storage=storage).delete(user)

    assert storage.calls
    assert db_session.get(User, user_id) is None


def test_a_learner_without_scenes_touches_no_store(deletable) -> None:
    db_session = deletable
    user = _user(db_session)
    storage = FakeStorage()
    UserService(db_session, image_storage=storage).delete(user)
    assert storage.calls == []


def test_local_store_removes_only_the_scenes_named(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_S3_BUCKET", None)
    gone, kept = uuid4(), uuid4()
    for scene_id in (gone, kept):
        folder = tmp_path / "scenes" / str(scene_id)
        folder.mkdir(parents=True)
        (folder / "panel-1-abc.webp").write_bytes(b"x")
        (folder / "page-0-def.webp").write_bytes(b"y")
    shared = tmp_path / "revue-plates"
    shared.mkdir()
    (shared / "cafe-123.webp").write_bytes(b"z")

    removed = GraphicNovelImageStorage().delete_scene_objects([gone, "../revue-plates"])

    assert removed == 2
    assert not (tmp_path / "scenes" / str(gone)).exists()
    assert (tmp_path / "scenes" / str(kept) / "panel-1-abc.webp").exists()
    assert (shared / "cafe-123.webp").exists()


class FakeS3:
    def __init__(self, keys: list[str]) -> None:
        self.keys = set(keys)
        self.deleted: list[str] = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        client = self

        class Paginator:
            def paginate(self, *, Bucket, Prefix):  # noqa: N803 - boto3 casing
                yield {"Contents": [{"Key": key} for key in sorted(client.keys) if key.startswith(Prefix)]}

        return Paginator()

    def delete_objects(self, *, Bucket, Delete):  # noqa: N803 - boto3 casing
        for item in Delete["Objects"]:
            self.keys.discard(item["Key"])
            self.deleted.append(item["Key"])
        return {}


def test_s3_store_deletes_the_scene_prefixes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_S3_BUCKET", "art-bucket")
    gone, kept = uuid4(), uuid4()
    fake = FakeS3(
        [
            f"scenes/{gone}/panel-1-a.webp",
            f"scenes/{gone}/panel-2-b.webp",
            f"scenes/{kept}/panel-1-c.webp",
            "revue-plates/cafe-1.webp",
        ]
    )
    monkeypatch.setattr(GraphicNovelImageStorage, "_s3_client", lambda self: fake)

    removed = GraphicNovelImageStorage().delete_scene_objects([gone])

    assert removed == 2
    assert fake.keys == {f"scenes/{kept}/panel-1-c.webp", "revue-plates/cafe-1.webp"}


def test_s3_failure_is_logged_not_raised(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_S3_BUCKET", "art-bucket")

    def boom(self):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(GraphicNovelImageStorage, "_s3_client", boom)

    assert GraphicNovelImageStorage().delete_scene_objects([uuid4()]) == 0
