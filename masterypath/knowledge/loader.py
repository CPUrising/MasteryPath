"""Knowledge base loader — read a folder of documents as topic sources.

M6.5 / folder knowledge base. Plain text only (``.txt`` / ``.md``) so there is
no extra dependency; PDF/DOCX can be added later behind the same interface.

Each file becomes a :class:`TopicSource`; its ``label`` is what a build payload
references in ``materials`` / ``sources``, and ``excerpt`` is what the outline
prompt shows the model.
"""

from __future__ import annotations

from pathlib import Path

from masterypath.learning.models import TopicSource

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".txt", ".md", ".markdown")
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build"}


def read_text(path: str | Path, *, max_bytes: int = 200_000) -> str:
    """Read a text file as UTF-8, replacing undecodable bytes."""
    data = Path(path).read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


def _excerpt(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def scan_folder(
    root: str | Path,
    *,
    exts: tuple[str, ...] = SUPPORTED_EXTENSIONS,
    recursive: bool = True,
    excerpt_chars: int = 500,
) -> list[TopicSource]:
    """Scan *root* and return one :class:`TopicSource` per supported file.

    Hidden files/dirs and common build dirs are skipped. Ordering is stable
    (sorted relative path).
    """
    base = Path(root)
    if not base.exists():
        raise FileNotFoundError(f"source folder not found: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"not a folder: {base}")

    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    for candidate in sorted(base.glob(pattern)):
        if not candidate.is_file():
            continue
        rel_parts = candidate.relative_to(base).parts
        if any(part.startswith(".") or part in _SKIP_DIRS for part in rel_parts):
            continue
        if candidate.suffix.lower() not in exts:
            continue
        files.append(candidate)

    sources: list[TopicSource] = []
    for index, file in enumerate(files):
        rel = file.relative_to(base).as_posix()
        sources.append(
            TopicSource(
                id=f"src:{rel}",
                kind="file",
                source_id=rel,
                label=rel,
                excerpt=_excerpt(read_text(file), excerpt_chars),
                position=index,
                available=True,
            )
        )
    return sources


def build_source_map(sources: list[TopicSource]) -> dict[str, str]:
    """``{label: id}`` plus basename aliases when unique (forgiving lookup)."""
    mapping = {source.label: source.id for source in sources}
    basenames: dict[str, list[str]] = {}
    for source in sources:
        basenames.setdefault(Path(source.label).name, []).append(source.id)
    for name, ids in basenames.items():
        if len(ids) == 1:
            mapping.setdefault(name, ids[0])
    return mapping


def selected_source_ids(sources: list[TopicSource]) -> set[str]:
    return {source.id for source in sources}


def load_folder(root: str | Path, **kwargs) -> tuple[list[TopicSource], dict[str, str], set[str]]:
    """Convenience: scan a folder and derive its map + selected ids."""
    sources = scan_folder(root, **kwargs)
    return sources, build_source_map(sources), selected_source_ids(sources)


__all__ = [
    "SUPPORTED_EXTENSIONS",
    "build_source_map",
    "load_folder",
    "read_text",
    "scan_folder",
    "selected_source_ids",
]
