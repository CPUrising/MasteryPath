"""Folder knowledge base loader — scan, map, attach, gaps."""

from __future__ import annotations

import pytest

from masterypath.knowledge.loader import (
    build_source_map,
    read_text,
    scan_folder,
    selected_source_ids,
)
from masterypath.learning.service import LearningService
from masterypath.learning.storage import LearningStore


@pytest.fixture()
def folder(tmp_path):
    root = tmp_path / "materials"
    (root / "sub").mkdir(parents=True)
    (root / "a.md").write_text("# Alpha\n\nconcurrency basics", encoding="utf-8")
    (root / "b.txt").write_text("Beta notes", encoding="utf-8")
    (root / "sub" / "c.md").write_text("Gamma nested", encoding="utf-8")
    (root / ".hidden.md").write_text("hidden", encoding="utf-8")
    (root / "d.pdf").write_bytes(b"%PDF-1.4 unsupported")
    return root


def test_scan_folder_finds_supported_files(folder):
    sources = scan_folder(folder)
    labels = [source.label for source in sources]
    assert labels == ["a.md", "b.txt", "sub/c.md"]
    assert all(source.kind == "file" for source in sources)
    assert sources[0].excerpt.startswith("# Alpha") or "Alpha" in sources[0].excerpt


def test_source_map_has_label_and_basename(folder):
    sources = scan_folder(folder)
    mapping = build_source_map(sources)
    assert mapping["a.md"] == "src:a.md"
    assert mapping["sub/c.md"] == "src:sub/c.md"
    assert mapping["c.md"] == "src:sub/c.md"  # unique basename alias
    assert selected_source_ids(sources) == {"src:a.md", "src:b.txt", "src:sub/c.md"}


def test_read_text_replaces_bad_bytes(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_bytes(b"ok \xff\xfe end")
    assert read_text(path).startswith("ok ")


def test_attach_sources_and_build_uses_them(folder):
    store = LearningStore(folder.parent / "db")
    service = LearningService(store)
    sources = service.attach_sources("p", scan_folder(folder))
    assert len(sources) == 3
    result = service.build(
        "p",
        {
            "modules": [
                {
                    "name": "M",
                    "materials": ["a.md"],
                    "knowledge_points": [
                        {"name": "grounded objective", "type": "concept", "sources": ["a.md"]}
                    ],
                }
            ]
        },
    )
    kinds = {gap.kind.value for gap in result.gaps}
    # a.md is used; b.txt and sub/c.md are omitted -> source_omission
    assert "source_omission" in kinds
    assert "goal_gap" not in kinds
    state = service.get_state("p")
    assert state["map"]["k1"]["grounding"] == "grounded"
    store.close()


def test_ungrounded_when_no_source(folder):
    store = LearningStore(folder.parent / "db2")
    service = LearningService(store)
    service.attach_sources("p", scan_folder(folder))
    result = service.build(
        "p",
        {"modules": [{"name": "M", "knowledge_points": [{"name": "no source", "type": "memory"}]}]},
    )
    assert any(gap.kind.value == "goal_gap" for gap in result.gaps)
    store.close()


def test_api_attach_and_list_sources(folder, tmp_path):
    from fastapi.testclient import TestClient

    from masterypath.api.app import create_app

    store = LearningStore(tmp_path / "api-db")
    app = create_app(store)
    with TestClient(app) as client:
        client.post("/learning/paths", json={"path_id": "p", "goal": "learn"})
        attached = client.post(
            "/learning/paths/p/sources", json={"folder": str(folder)}
        ).json()
        assert len(attached) == 3
        listed = client.get("/learning/paths/p/sources").json()
        assert {source["label"] for source in listed} == {"a.md", "b.txt", "sub/c.md"}
    store.close()
