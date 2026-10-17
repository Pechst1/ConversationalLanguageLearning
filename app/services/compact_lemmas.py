"""The French lemmatizer's lookup tables in ~6 MB instead of ~150 MB (#134).

``fr_core_news_sm`` ships its rule lemmatizer with four lookup tables: a
217k-entry form → lemma table, per-POS exception tables (51k entries) and per-POS
word lists. spaCy loads them into ``OrderedDict`` tables of Python strings and
lists, ~150 MB resident, which is a third of the 512 MB instance the API and the
worker run on, and why both were killed for memory.

The same data fits in a few NumPy arrays: sorted 64-bit key hashes, offsets and
one UTF-8 blob per table. :func:`build` writes them once next to the installed
model (the Docker build does it); :func:`attach` loads the pipeline without its
lemmatizer and adds one that reads these arrays. Keys are hashed with spaCy's
own ``get_string_id``, exactly as its ``Table`` does, so every lookup answers
what the original table answered (``tests/test_compact_lemmas.py``).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

DIRNAME = "compact_lemmas"
FORMAT = 1
_SEP = "\x00"


def _string_id(key: Any) -> int:
    from spacy.strings import get_string_id

    return int(get_string_id(key))


class _Packed:
    """A frozen ``hash → list[str]`` map: sorted keys, offsets, one blob."""

    __slots__ = ("keys", "offsets", "blob")

    def __init__(self, keys: np.ndarray, offsets: np.ndarray, blob: bytes) -> None:
        self.keys = keys
        self.offsets = offsets
        self.blob = blob

    @classmethod
    def from_items(cls, items: Iterable[tuple[int, Iterable[str]]]) -> _Packed:
        rows = sorted((int(k), _SEP.join(v).encode("utf-8")) for k, v in items)
        keys = np.fromiter((k for k, _ in rows), dtype=np.uint64, count=len(rows))
        lengths = np.fromiter((len(b) for _, b in rows), dtype=np.int64, count=len(rows))
        offsets = np.zeros(len(rows) + 1, dtype=np.int64)
        np.cumsum(lengths, out=offsets[1:])
        return cls(keys, offsets, b"".join(b for _, b in rows))

    def _find(self, key: Any) -> int:
        h = np.uint64(_string_id(key))
        i = int(np.searchsorted(self.keys, h))
        return i if i < len(self.keys) and self.keys[i] == h else -1

    def __contains__(self, key: Any) -> bool:
        return self._find(key) >= 0

    def get(self, key: Any, default: Any = None) -> Any:
        i = self._find(key)
        if i < 0:
            return default
        return self.blob[self.offsets[i]:self.offsets[i + 1]].decode("utf-8").split(_SEP)

    def __getitem__(self, key: Any) -> Any:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __len__(self) -> int:
        return len(self.keys)

    def __bool__(self) -> bool:
        return len(self.keys) > 0

    def save(self, path: Path) -> None:
        np.save(path / "keys.npy", self.keys)
        np.save(path / "offsets.npy", self.offsets)
        (path / "blob.bin").write_bytes(self.blob)

    @classmethod
    def load(cls, path: Path) -> _Packed:
        return cls(np.load(path / "keys.npy"), np.load(path / "offsets.npy"), (path / "blob.bin").read_bytes())


class _WordSet:
    """A frozen word list (``string in index``): sorted 64-bit hashes."""

    __slots__ = ("keys",)

    def __init__(self, keys: np.ndarray) -> None:
        self.keys = keys

    def __contains__(self, word: Any) -> bool:
        h = np.uint64(_string_id(word))
        i = int(np.searchsorted(self.keys, h))
        return i < len(self.keys) and self.keys[i] == h

    def __len__(self) -> int:
        return len(self.keys)

    def __bool__(self) -> bool:
        return len(self.keys) > 0


_MISSING = object()


class _ByPos(dict):
    """``table.get(univ_pos)`` → the per-POS object; keys hashed as spaCy's Table does."""

    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        return dict.get(self, _string_id(key), default)

    def __contains__(self, key: Any) -> bool:  # type: ignore[override]
        return dict.__contains__(self, _string_id(key))

    def __getitem__(self, key: Any) -> Any:
        return dict.__getitem__(self, _string_id(key))


def model_dir(model: str) -> Path:
    from spacy.util import get_package_path

    return Path(get_package_path(model))


def tables_dir(model: str) -> Path:
    return model_dir(model) / DIRNAME


def build(model: str, out: Path | None = None) -> Path:
    """Write the compact tables for ``model`` (loads the full pipeline once)."""

    import spacy

    nlp = spacy.load(model, exclude=["tok2vec", "morphologizer", "parser", "attribute_ruler", "ner"])
    lookups = nlp.get_pipe("lemmatizer").lookups
    out = out or tables_dir(model)
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"format": FORMAT, "model": model, "version": nlp.meta.get("version"), "tables": {}}

    lookup = lookups.get_table("lemma_lookup")
    target = out / "lemma_lookup"
    target.mkdir(exist_ok=True)
    _Packed.from_items((k, v if isinstance(v, list) else [v]) for k, v in lookup.items()).save(target)
    manifest["tables"]["lemma_lookup"] = "packed"

    index = lookups.get_table("lemma_index")
    index_out: dict[str, int] = {}
    for n, (pos_key, words) in enumerate(index.items()):
        keys = np.unique(np.fromiter((_string_id(w) for w in words), dtype=np.uint64))
        np.save(out / f"lemma_index_{n}.npy", keys)
        index_out[str(int(pos_key))] = n
    manifest["tables"]["lemma_index"] = index_out

    exc = lookups.get_table("lemma_exc")
    exc_out: dict[str, int] = {}
    for n, (pos_key, mapping) in enumerate(exc.items()):
        target = out / f"lemma_exc_{n}"
        target.mkdir(exist_ok=True)
        _Packed.from_items((_string_id(w), lemmas) for w, lemmas in mapping.items()).save(target)
        exc_out[str(int(pos_key))] = n
    manifest["tables"]["lemma_exc"] = exc_out

    # Three short suffix lists: kept as they are.
    rules = {str(int(k)): v for k, v in lookups.get_table("lemma_rules").items()}
    (out / "lemma_rules.json").write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out


def load_lookups(path: Path) -> Any:
    """A spaCy ``Lookups`` whose tables read the compact arrays."""

    from spacy.lookups import Lookups

    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError(f"compact lemma tables at {path} have format {manifest.get('format')}, not {FORMAT}")
    tables = manifest["tables"]
    lookups = Lookups()
    lookups._tables["lemma_lookup"] = _Packed.load(path / "lemma_lookup")  # noqa: SLF001
    index = _ByPos()
    for pos_key, n in tables["lemma_index"].items():
        index[int(pos_key)] = _WordSet(np.load(path / f"lemma_index_{n}.npy"))
    lookups._tables["lemma_index"] = index  # noqa: SLF001
    exc = _ByPos()
    for pos_key, n in tables["lemma_exc"].items():
        exc[int(pos_key)] = _Packed.load(path / f"lemma_exc_{n}")
    lookups._tables["lemma_exc"] = exc  # noqa: SLF001
    rules = _ByPos()
    for pos_key, value in json.loads((path / "lemma_rules.json").read_text(encoding="utf-8")).items():
        rules[int(pos_key)] = value
    lookups._tables["lemma_rules"] = rules  # noqa: SLF001
    return lookups


def load(model: str, path: Path | None = None) -> Any:
    """The pipeline with its lemmatizer reading the compact tables.

    Raises ``FileNotFoundError`` when they were never built, so the caller falls
    back to the plain ``spacy.load``.
    """

    import spacy

    path = path or tables_dir(model)
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    nlp = spacy.load(model, exclude=["lemmatizer"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != nlp.meta.get("version"):
        raise FileNotFoundError(f"compact lemma tables are for {model} {manifest.get('version')}")
    config = {k: v for k, v in nlp.config["components"].get("lemmatizer", {}).items() if k != "factory"}
    config = config or {"mode": "rule", "overwrite": False}
    after = "attribute_ruler" if "attribute_ruler" in nlp.pipe_names else None
    lemmatizer = nlp.add_pipe("lemmatizer", config=config, after=after) if after else nlp.add_pipe("lemmatizer", config=config)
    lemmatizer.lookups = load_lookups(path)
    lemmatizer._validate_tables()  # noqa: SLF001
    return nlp


if __name__ == "__main__":  # python -m app.services.compact_lemmas [model]
    import sys

    target_model = sys.argv[1] if len(sys.argv) > 1 else "fr_core_news_sm"
    print(f"compact lemma tables written to {build(target_model)}")
