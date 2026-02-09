from __future__ import annotations

import os
import re
import sys
import csv
import json
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Dict, Literal

from tqdm import tqdm
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from ..db import get_engine
from ..language import (
    UNKNOWN_LANGUAGE,
    configured_supported_languages,
    infer_language_from_text,
    normalize_language_tag,
)
from ..settings import settings
from ..clients.opensearch_client import ensure_write_index_target, get_opensearch
from ..clients.qdrant_client import get_qdrant
from ..text_normalization import normalize_arabic_script
# Embeddings
from sentence_transformers import SentenceTransformer


LOG = logging.getLogger("openiti.ingest")


# ---------------------------
# Config
# ---------------------------

DEFAULT_TARGET_WORKS = int(os.getenv("INGEST_WORK_LIMIT", "200") or "200")
DEFAULT_ONLY_PRI = os.getenv("INGEST_ONLY_PRI", "true").lower() in ("1", "true", "yes")
DEFAULT_LANGS = [
    normalize_language_tag(v)
    for v in os.getenv("INGEST_LANGS", settings.SUPPORTED_LANGUAGES).split(",")
    if v.strip()
]
if not DEFAULT_LANGS:
    DEFAULT_LANGS = configured_supported_languages()
CHUNK_TARGET_WORDS = int(os.getenv("CHUNK_TARGET_WORDS", "300") or "300")
CHUNK_MAX_OVERLAP_WORDS = int(os.getenv("CHUNK_MAX_OVERLAP_WORDS", "0") or "0")
SKIP_EXISTING = os.getenv("SKIP_EXISTING", "true").lower() in ("1", "true", "yes")

EMBEDDINGS_ENABLED = os.getenv("EMBEDDINGS_ENABLED", "true").lower() in ("1", "true", "yes")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu").lower()
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64") or "64")
EMBEDDING_MODEL_ID = os.getenv(
    "EMBEDDING_MODEL",
    # solid multilingual baseline, Arabic-script friendly
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

# OpenSearch bulk sizing
OS_BULK_BATCH = int(os.getenv("OPENSEARCH_BULK_BATCH", "500") or "500")

# Curated tags (for faceting)
CURATED_TAGS_PATH = os.getenv("CURATED_TAGS_PATH", "")

INGEST_FLOW_ORDER = ("discovered", "parsed", "indexed_bm25", "embedded", "complete")


@dataclass(frozen=True)
class IngestStateRow:
    version_id: str
    status: str
    last_chunk_index: int | None


@dataclass(frozen=True)
class IngestDecision:
    action: Literal["process", "resume", "skip_complete"]
    start_chunk_index: int
    reason: str


@dataclass(frozen=True)
class SectionBlock:
    heading_text: str | None
    heading_path: list[str] | None
    word_spans: list[tuple[int, int]]


@dataclass(frozen=True)
class PlannedChunk:
    chunk_index: int
    heading_text: str | None
    heading_path: list[str] | None
    start_char_offset: int
    end_char_offset: int
    text_raw: str
    text_norm: str
    word_count: int


# ---------------------------
# Metadata loading + facets
# ---------------------------

REGION_PRECEDENCE = ("born@", "resided@", "died@", "visited@")

def _repo_root() -> Path:
    # /app/apps/api/app/ingest/run.py -> /app
    return Path(__file__).resolve().parents[4]


def _normalize_repo_path(p: str) -> str:
    p = (p or "").strip().replace("\\", "/")
    while p.startswith("../"):
        p = p[3:]
    if p.startswith("./"):
        p = p[2:]
    return p


def _load_curated_tags() -> set[str]:
    if CURATED_TAGS_PATH:
        path = Path(CURATED_TAGS_PATH)
    else:
        path = _repo_root() / "curated_tags.txt"
    if not path.exists():
        LOG.warning("Curated tags list not found at %s; tags facet will be empty.", path)
        return set()
    with path.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _ah_to_ce(ah: int) -> int:
    # Approximate conversion; sufficient for display facet
    return int(round(ah * 0.97023 + 621.57))


def _extract_period(tags: list[str]) -> tuple[str | None, str | None]:
    period_tag = next((t for t in tags if t.startswith("GAL@period-")), None)
    if not period_tag:
        return None, None
    label = period_tag.replace("GAL@period-", "").replace("-", " ").strip()
    return period_tag, label


def _extract_region(tags: list[str]) -> list[str]:
    for prefix in REGION_PRECEDENCE:
        vals = []
        for t in tags:
            if t.startswith(prefix) and t.endswith("_RE"):
                val = t[len(prefix):-3].strip()
                if val:
                    vals.append(val)
        if vals:
            return sorted(set(vals))
    return []


def _filter_curated_tags(tags: list[str], curated: set[str]) -> list[str]:
    if not curated:
        return []
    return [t for t in tags if t in curated]


def _version_label(status: str | None) -> str | None:
    if not status:
        return None
    if status == "pri":
        return "PRI"
    if status == "sec":
        return "ALT"
    return status.upper()


def _metadata_is_pri(status: str | None, version_label: str | None, fallback: bool) -> bool:
    status_norm = (status or "").strip().lower()
    version_norm = (version_label or "").strip().upper()
    if status_norm == "pri" or version_norm == "PRI":
        return True
    if status_norm == "sec" or version_norm == "ALT":
        return False
    return fallback


def _metadata_language(row: dict) -> tuple[str, str | None]:
    candidates = [
        row.get("language"),
        row.get("lang"),
        row.get("lang_code"),
        row.get("language_code"),
        row.get("iso_lang"),
    ]
    for candidate in candidates:
        if candidate and str(candidate).strip():
            return normalize_language_tag(str(candidate)), str(candidate)
    return UNKNOWN_LANGUAGE, None


def _infer_language_from_path(repo_path: str) -> str:
    return infer_language_from_text(repo_path)


def load_metadata(corpus_root: Path, curated_tags: set[str]) -> tuple[dict[str, dict], dict[str, dict]]:
    csv_path = corpus_root / "OpenITI_metadata_2023-1-8.csv"
    if not csv_path.exists():
        LOG.warning("Metadata CSV not found at %s; skipping metadata enrichment.", csv_path)
        return {}, {}

    by_path: dict[str, dict] = {}
    by_version: dict[str, dict] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            local_path = _normalize_repo_path(row.get("local_path") or "")
            version_uri = (row.get("version_uri") or "").strip()
            lang_from_row, raw_lang = _metadata_language(row)
            inferred_lang = _infer_language_from_path(local_path or version_uri)
            normalized_lang = lang_from_row if lang_from_row != UNKNOWN_LANGUAGE else inferred_lang
            tags_raw = [t.strip() for t in (row.get("tags") or "").split(" :: ") if t.strip()]

            period_tag, period_label = _extract_period(tags_raw)
            region_vals = _extract_region(tags_raw)
            curated = _filter_curated_tags(tags_raw, curated_tags)

            date_ah = _parse_int(row.get("date"))
            date_ce = _ah_to_ce(date_ah) if date_ah is not None else None

            meta = {
                "author_ar": (row.get("author_ar") or "").strip() or None,
                "author_lat": (row.get("author_lat") or "").strip() or None,
                "author_lat_shuhra": (row.get("author_lat_shuhra") or "").strip() or None,
                "author_lat_full_name": (row.get("author_lat_full_name") or "").strip() or None,
                "work_title_ar": (row.get("title_ar") or "").strip() or None,
                "work_title_lat": (row.get("title_lat") or "").strip() or None,
                "book": (row.get("book") or "").strip() or None,
                "status": (row.get("status") or "").strip() or None,
                "version_label": _version_label((row.get("status") or "").strip()),
                "lang": normalized_lang,
                "lang_raw": raw_lang,
                "date_ah": date_ah,
                "date_ce": date_ce,
                "period_tag": period_tag,
                "period": period_label,
                "region": region_vals,
                "tags": curated,
                "tags_raw": tags_raw,
                "local_path": local_path or None,
                "ed_info": (row.get("ed_info") or "").strip() or None,
                "id": (row.get("id") or "").strip() or None,
            }

            if local_path:
                by_path[local_path] = meta
            if version_uri:
                by_version[version_uri] = meta

    LOG.info("Loaded metadata: %d by path, %d by version", len(by_path), len(by_version))
    return by_path, by_version


# ---------------------------
# Discovery model
# ---------------------------

@dataclass(frozen=True)
class DiscoveredText:
    author_id: str
    work_id: str
    version_id: str
    repo_path: str  # path relative to CORPUS_ROOT
    abs_path: Path
    is_pri: bool
    lang: str  # canonical language tag (ar/en/fa/unknown)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_openiti_text(head: str) -> bool:
    # Many OpenITI texts begin with OpenITI markers like "######OpenITI#"
    return "OpenITI" in head or "######OpenITI" in head or "######" in head


def iter_text_files(corpus_root: Path) -> Iterator[Path]:
    data_dir = corpus_root / "data"
    if not data_dir.exists():
        raise RuntimeError(f"Expected {data_dir} to exist (CORPUS_ROOT should point at RELEASE repo).")

    # OpenITI files can have various extensions; accept broadly but skip obvious non-text.
    for p in data_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        # Skip huge binary-ish artifacts
        if p.suffix.lower() in (".jpg", ".png", ".pdf", ".zip", ".gz", ".tar", ".sqlite", ".db"):
            continue
        yield p


def infer_ids_from_path(corpus_root: Path, file_path: Path) -> Tuple[str, str, str, str]:
    """
    Infer OpenITI-style ids from path: data/<author>/<work>/<version_file>
    Returns: (author_id, work_id, version_id, repo_rel_path)
    """
    rel = file_path.relative_to(corpus_root).as_posix()

    parts = file_path.relative_to(corpus_root / "data").parts
    if len(parts) < 3:
        # fall back to something stable-ish
        base = file_path.stem
        author_id = "unknown_author"
        work_id = f"unknown_work::{base}"
        version_id = f"{work_id}::{base}"
        return author_id, work_id, version_id, rel

    author_dir = parts[0]
    work_dir = parts[1]
    version_file = parts[-1]

    # Use directory names as IDs (OpenITI uses structured IDs; this preserves stability)
    author_id = author_dir
    work_id = f"{author_dir}.{work_dir}"
    version_id = f"{work_id}.{Path(version_file).stem}"

    return author_id, work_id, version_id, rel


def choose_pri_versions(files_by_workdir: Dict[Path, List[Path]]) -> List[Path]:
    """
    If a work has multiple version files, prefer any that include PRI/pri in filename.
    If only one file exists, treat it as PRI.
    """
    chosen: List[Path] = []
    for workdir, files in files_by_workdir.items():
        if len(files) == 1:
            chosen.append(files[0])
            continue
        pri = [f for f in files if "PRI" in f.name or "pri" in f.name]
        chosen.append(pri[0] if pri else files[0])
    return chosen


def _pri_score(path: Path, status: str | None) -> int:
    score = 0
    if (status or "").lower() == "pri":
        score += 2
    if "pri" in path.name.lower():
        score += 1
    return score


def _resolve_local_path(corpus_root: Path, local_path: str) -> tuple[str, Path] | tuple[None, None]:
    rel = _normalize_repo_path(local_path)
    if not rel:
        return None, None
    if not rel.startswith("data/"):
        rel = f"data/{rel}"
    abs_path = (corpus_root / rel).resolve()
    if not abs_path.is_file():
        return None, None
    return rel, abs_path


def _supports_ingest_language(lang: str) -> bool:
    normalized = normalize_language_tag(lang)
    return normalized == UNKNOWN_LANGUAGE or normalized in DEFAULT_LANGS


def _select_with_min_two_languages(
    candidates: list[tuple[Path, str, str | None, dict]],
    *,
    target_works: int,
) -> list[tuple[Path, str, str | None, dict]]:
    if target_works <= 0 or not candidates:
        return []

    ordered = sorted(candidates, key=lambda t: t[1])
    by_lang: dict[str, list[tuple[Path, str, str | None, dict]]] = {}
    for item in ordered:
        lang = normalize_language_tag(item[3].get("lang"))
        by_lang.setdefault(lang, []).append(item)

    usable_langs = [lang for lang, items in by_lang.items() if items and lang != UNKNOWN_LANGUAGE]
    if len(usable_langs) < 2:
        return ordered[:target_works]

    selected: list[tuple[Path, str, str | None, dict]] = []
    used_repo_paths: set[str] = set()
    for lang in usable_langs[:2]:
        choice = by_lang[lang][0]
        selected.append(choice)
        used_repo_paths.add(choice[1])

    for item in ordered:
        if len(selected) >= target_works:
            break
        if item[1] in used_repo_paths:
            continue
        selected.append(item)
        used_repo_paths.add(item[1])
    return selected


def _discover_from_metadata_index(
    corpus_root: Path,
    target_works: int,
    metadata_by_path: dict[str, dict],
) -> List[DiscoveredText]:
    if not metadata_by_path or target_works <= 0:
        return []

    selected_by_work: dict[tuple[str, str], tuple[Path, str, str | None, int, dict]] = {}
    all_files: list[tuple[Path, str, str | None, dict]] = []

    for local_path, meta in metadata_by_path.items():
        repo_rel, abs_path = _resolve_local_path(corpus_root, local_path)
        if not repo_rel or not abs_path:
            continue
        try:
            rel_parts = abs_path.relative_to(corpus_root / "data").parts
        except Exception:
            continue
        if len(rel_parts) < 3:
            continue

        resolved_lang = normalize_language_tag(meta.get("lang"))
        if not _supports_ingest_language(resolved_lang):
            continue

        status = (meta.get("status") or "").strip().lower() or None
        work_key = (rel_parts[0], rel_parts[1])
        score = _pri_score(abs_path, status)

        if DEFAULT_ONLY_PRI:
            if score <= 0:
                continue
            prev = selected_by_work.get(work_key)
            if prev is None or score > prev[3] or (score == prev[3] and repo_rel < prev[1]):
                selected_by_work[work_key] = (abs_path, repo_rel, status, score, meta)
        else:
            all_files.append((abs_path, repo_rel, status, meta))

    if DEFAULT_ONLY_PRI:
        selected = sorted(selected_by_work.values(), key=lambda t: t[1])[:target_works]
        files = [(t[0], t[1], t[2], t[4]) for t in selected]
    else:
        files = _select_with_min_two_languages(all_files, target_works=target_works)

    discovered: List[DiscoveredText] = []
    for fp, repo_rel, status, meta in files:
        author_id, work_id, version_id, _ = infer_ids_from_path(corpus_root, fp)
        metadata_lang = normalize_language_tag(meta.get("lang"))
        if metadata_lang == UNKNOWN_LANGUAGE:
            LOG.warning(
                "Language metadata missing/unmapped for %s (raw=%s). Using unknown.",
                repo_rel,
                meta.get("lang_raw"),
            )

        discovered.append(
            DiscoveredText(
                author_id=author_id,
                work_id=work_id,
                version_id=version_id,
                repo_path=repo_rel,
                abs_path=fp,
                is_pri=_metadata_is_pri(
                    status=(status or "") if status else None,
                    version_label=(meta.get("version_label") or "") if meta else None,
                    fallback=("pri" in fp.name.lower()),
                ),
                lang=metadata_lang,
            )
        )
        if len(discovered) >= target_works:
            break
    return discovered


def discover_200_pri_arabic(
    corpus_root: Path,
    target_works: int,
    *,
    metadata_by_path: dict[str, dict] | None = None,
) -> List[DiscoveredText]:
    """
    Discover texts by walking data/ and selecting up to target_works versions.
    """
    if metadata_by_path:
        discovered = _discover_from_metadata_index(corpus_root, target_works, metadata_by_path)
        if discovered:
            LOG.info("Discovery used metadata index: %d texts", len(discovered))
            return discovered

    # Fallback: filesystem walk.
    # Group by work directory: data/<author>/<work>/
    files_by_workdir: Dict[Path, List[Path]] = {}
    pri_by_workdir: Dict[Path, Path] = {}
    first_by_workdir: Dict[Path, Path] = {}
    for fp in iter_text_files(corpus_root):
        # read small head to ensure it's text-like
        try:
            head = fp.open("r", encoding="utf-8", errors="ignore").read(4096)
        except Exception:
            continue
        if not looks_like_openiti_text(head):
            continue

        # Work dir = data/<author>/<work>/
        try:
            rel_parts = fp.relative_to(corpus_root / "data").parts
        except Exception:
            continue
        if len(rel_parts) < 3:
            continue
        workdir = (corpus_root / "data" / rel_parts[0] / rel_parts[1])
        files_by_workdir.setdefault(workdir, []).append(fp)

        if DEFAULT_ONLY_PRI:
            if workdir not in first_by_workdir:
                first_by_workdir[workdir] = fp
            if "pri" in fp.name.lower() and workdir not in pri_by_workdir:
                pri_by_workdir[workdir] = fp
                if len(pri_by_workdir) >= target_works:
                    break

    if DEFAULT_ONLY_PRI:
        pri_files = list(pri_by_workdir.values())
        if len(pri_files) < target_works:
            for workdir, fp in first_by_workdir.items():
                if workdir in pri_by_workdir:
                    continue
                pri_files.append(fp)
                if len(pri_files) >= target_works:
                    break
    else:
        pri_files = [f for fs in files_by_workdir.values() for f in fs]

    fallback_candidates: list[tuple[Path, str, bool, str]] = []
    discovered: List[DiscoveredText] = []
    for fp in pri_files:
        author_id, work_id, version_id, repo_rel = infer_ids_from_path(corpus_root, fp)

        lang = _infer_language_from_path(repo_rel)
        if not _supports_ingest_language(lang):
            continue
        if lang == UNKNOWN_LANGUAGE:
            LOG.warning("Language metadata missing/unmapped for %s. Using unknown.", repo_rel)

        # Mark PRI by filename heuristic or single-file selection
        is_pri = True if (("PRI" in fp.name) or ("pri" in fp.name)) else DEFAULT_ONLY_PRI
        fallback_candidates.append((fp, repo_rel, is_pri, lang))

    selected_candidates = _select_with_min_two_languages(
        [
            (
                fp,
                repo_rel,
                None,
                {"lang": lang},
            )
            for fp, repo_rel, _is_pri, lang in fallback_candidates
        ],
        target_works=target_works,
    )
    selected_lookup = {repo_rel for _, repo_rel, _, _ in selected_candidates}

    for fp, repo_rel, is_pri, lang in fallback_candidates:
        if repo_rel not in selected_lookup:
            continue
        author_id, work_id, version_id, _ = infer_ids_from_path(corpus_root, fp)

        discovered.append(
            DiscoveredText(
                author_id=author_id,
                work_id=work_id,
                version_id=version_id,
                repo_path=repo_rel,
                abs_path=fp,
                is_pri=is_pri,
                lang=lang,
            )
        )
        if len(discovered) >= target_works:
            break

    return discovered


# ---------------------------
# Chunking
# ---------------------------

def chunk_words(words: List[str], target: int, overlap: int) -> Iterator[Tuple[int, int, List[str]]]:
    """
    Yield (start_word_idx, end_word_idx, words_slice)
    """
    if target <= 0:
        raise ValueError("target must be > 0")
    step = target - overlap if target > overlap else target
    i = 0
    n = len(words)
    chunk_index = 0
    while i < n:
        j = min(i + target, n)
        yield (chunk_index, i, words[i:j])
        chunk_index += 1
        i += step


HEADING_LINE_RE = re.compile(r"^(?P<hashes>#{1,6})\s*(?P<body>.+?)\s*$")
WORD_RE = re.compile(r"\S+")


def _parse_heading_line(line: str) -> tuple[int, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("######OpenITI#"):
        return None

    match = HEADING_LINE_RE.match(stripped)
    if not match:
        return None

    level = len(match.group("hashes"))
    body = match.group("body").strip().lstrip("|").strip()
    if not body or body.startswith("OpenITI#"):
        return None
    return level, body


def _build_section_blocks(raw: str) -> list[SectionBlock]:
    sections: list[SectionBlock] = [SectionBlock(heading_text=None, heading_path=None, word_spans=[])]
    heading_stack: list[str] = []
    cursor = 0

    for line in raw.splitlines(keepends=True):
        line_start = cursor
        if line.strip().startswith("######OpenITI#"):
            cursor += len(line)
            continue
        heading = _parse_heading_line(line)
        if heading is not None:
            level, heading_text = heading
            if level <= 0:
                level = 1
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading_text)
            sections.append(
                SectionBlock(
                    heading_text=heading_text,
                    heading_path=list(heading_stack),
                    word_spans=[],
                )
            )
        else:
            word_spans = list(sections[-1].word_spans)
            for m in WORD_RE.finditer(line):
                word_spans.append((line_start + m.start(), line_start + m.end()))
            sections[-1] = SectionBlock(
                heading_text=sections[-1].heading_text,
                heading_path=sections[-1].heading_path,
                word_spans=word_spans,
            )
        cursor += len(line)

    return sections


def build_chunk_plan(raw: str, *, target_words: int, overlap_words: int) -> list[PlannedChunk]:
    sections = _build_section_blocks(raw)
    chunks: list[PlannedChunk] = []
    next_chunk_index = 0

    for section in sections:
        if not section.word_spans:
            continue
        section_words = [raw[s:e] for s, e in section.word_spans]
        for _local_index, start_word, wslice in chunk_words(section_words, target_words, overlap_words):
            if not wslice:
                continue
            end_word = start_word + len(wslice) - 1
            start_char = section.word_spans[start_word][0]
            end_char = section.word_spans[end_word][1]
            text_raw = raw[start_char:end_char]
            text_norm = normalize_arabic_script(text_raw)
            if not text_norm:
                continue
            chunks.append(
                PlannedChunk(
                    chunk_index=next_chunk_index,
                    heading_text=section.heading_text,
                    heading_path=section.heading_path,
                    start_char_offset=start_char,
                    end_char_offset=end_char,
                    text_raw=text_raw,
                    text_norm=text_norm,
                    word_count=len(wslice),
                )
            )
            next_chunk_index += 1
    return chunks


def extract_heading_context(text: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Minimal mARkdown heading extraction:
    - Looks for lines that resemble headings and keeps the most recent.
    This is intentionally simple; replace later with a real parser.
    """
    heading = None
    path = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Very loose: treat markdown-like headings or OpenITI heading markers as headings
        if line.startswith("#") or line.startswith("###") or "### " in line:
            heading = re.sub(r"^#+\s*", "", line).strip()
            if heading:
                path = [heading]
    return heading, path or None


def read_text_file(fp: Path) -> str:
    return fp.read_text(encoding="utf-8", errors="ignore")


# ---------------------------
# Postgres upserts
# ---------------------------

def upsert_author(
    engine: Engine,
    author_id: str,
    *,
    name_ar: str | None = None,
    name_latn: str | None = None,
    metadata: dict | None = None,
) -> None:
    meta = metadata or {}
    sql = text(
        """
        INSERT INTO authors(author_id, name_ar, name_latn, metadata)
        VALUES (:author_id, :name_ar, :name_latn, :metadata)
        ON CONFLICT (author_id) DO UPDATE
          SET name_ar = COALESCE(EXCLUDED.name_ar, authors.name_ar),
              name_latn = COALESCE(EXCLUDED.name_latn, authors.name_latn),
              metadata = authors.metadata || EXCLUDED.metadata
        """
    ).bindparams(bindparam("metadata", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "author_id": author_id,
                "name_ar": name_ar,
                "name_latn": name_latn,
                "metadata": json.dumps(meta, ensure_ascii=False),
            },
        )


def upsert_work(
    engine: Engine,
    work_id: str,
    author_id: str,
    *,
    title_ar: str | None = None,
    title_latn: str | None = None,
    metadata: dict | None = None,
) -> None:
    meta = metadata or {}
    sql = text(
        """
        INSERT INTO works(work_id, author_id, title_ar, title_latn, metadata)
        VALUES (:work_id, :author_id, :title_ar, :title_latn, :metadata)
        ON CONFLICT (work_id) DO UPDATE
          SET author_id = EXCLUDED.author_id,
              title_ar = COALESCE(EXCLUDED.title_ar, works.title_ar),
              title_latn = COALESCE(EXCLUDED.title_latn, works.title_latn),
              metadata = works.metadata || EXCLUDED.metadata
        """
    ).bindparams(bindparam("metadata", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "work_id": work_id,
                "author_id": author_id,
                "title_ar": title_ar,
                "title_latn": title_latn,
                "metadata": json.dumps(meta, ensure_ascii=False),
            },
        )


def upsert_version(
    engine: Engine,
    t: DiscoveredText,
    checksum: str | None,
    word_count: int | None,
    char_count: int | None,
    *,
    metadata: dict | None = None,
) -> None:
    meta = metadata or {}
    sql = text(
        """
        INSERT INTO versions(version_id, work_id, is_pri, lang, repo_path, checksum_sha256, word_count, char_count, metadata)
        VALUES (:version_id, :work_id, :is_pri, :lang, :repo_path, :checksum, :word_count, :char_count, :metadata)
        ON CONFLICT (version_id) DO UPDATE
          SET work_id = EXCLUDED.work_id,
              is_pri = EXCLUDED.is_pri,
              lang = EXCLUDED.lang,
              repo_path = EXCLUDED.repo_path,
              checksum_sha256 = EXCLUDED.checksum_sha256,
              word_count = EXCLUDED.word_count,
              char_count = EXCLUDED.char_count,
              metadata = versions.metadata || EXCLUDED.metadata
        """
    ).bindparams(bindparam("metadata", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "version_id": t.version_id,
                "work_id": t.work_id,
                "is_pri": t.is_pri,
                "lang": t.lang,
                "repo_path": t.repo_path,
                "checksum": checksum,
                "word_count": word_count,
                "char_count": char_count,
                "metadata": json.dumps(meta, ensure_ascii=False),
            },
        )


def get_version_row(engine: Engine, version_id: str) -> dict | None:
    sql = text(
        """
        SELECT version_id, lang, is_pri, metadata
        FROM versions
        WHERE version_id = :version_id
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql, {"version_id": version_id}).mappings().first()
    return dict(row) if row else None


def get_ingest_state(engine: Engine, version_id: str) -> IngestStateRow | None:
    sql = text(
        """
        SELECT version_id, status, last_chunk_index
        FROM ingest_state
        WHERE version_id = :version_id
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql, {"version_id": version_id}).mappings().first()
    if not row:
        return None
    return IngestStateRow(
        version_id=row["version_id"],
        status=row["status"],
        last_chunk_index=row["last_chunk_index"],
    )


def _flow_rank(status: str) -> int:
    if status not in INGEST_FLOW_ORDER:
        return -1
    return INGEST_FLOW_ORDER.index(status)


def is_valid_ingest_transition(current_status: str | None, next_status: str) -> bool:
    if not current_status:
        return next_status == "discovered"
    if current_status == next_status:
        return True
    if current_status == "failed":
        return next_status in ("discovered", "failed")
    if next_status == "failed":
        return True
    if current_status == "complete":
        return next_status in ("complete", "discovered")
    cur_rank = _flow_rank(current_status)
    next_rank = _flow_rank(next_status)
    return cur_rank >= 0 and next_rank >= 0 and next_rank >= cur_rank


def decide_ingest_behavior(
    state: IngestStateRow | None,
    *,
    skip_existing: bool,
    embeddings_enabled: bool,
) -> IngestDecision:
    if state is None:
        return IngestDecision(action="process", start_chunk_index=0, reason="no_checkpoint")
    if state.status == "complete":
        if skip_existing:
            return IngestDecision(action="skip_complete", start_chunk_index=0, reason="already_complete")
        return IngestDecision(action="process", start_chunk_index=0, reason="forced_reprocess_complete")

    if not skip_existing:
        return IngestDecision(action="process", start_chunk_index=0, reason=f"forced_reprocess_{state.status}")

    if state.status == "embedded":
        if state.last_chunk_index is None:
            return IngestDecision(action="process", start_chunk_index=0, reason="embedded_missing_last_chunk")
        return IngestDecision(action="resume", start_chunk_index=state.last_chunk_index + 1, reason="resume_from_embedded")

    if state.status == "indexed_bm25":
        if state.last_chunk_index is None:
            return IngestDecision(action="process", start_chunk_index=0, reason="indexed_missing_last_chunk")
        if embeddings_enabled:
            return IngestDecision(action="resume", start_chunk_index=state.last_chunk_index, reason="resume_replay_last_for_embedding")
        return IngestDecision(action="resume", start_chunk_index=state.last_chunk_index + 1, reason="resume_from_indexed_bm25")

    if state.status == "failed" and state.last_chunk_index is not None:
        if embeddings_enabled:
            return IngestDecision(action="resume", start_chunk_index=state.last_chunk_index, reason="resume_failed_replay_last")
        return IngestDecision(action="resume", start_chunk_index=state.last_chunk_index + 1, reason="resume_failed_from_checkpoint")

    return IngestDecision(action="process", start_chunk_index=0, reason=f"restart_from_{state.status}")


def set_ingest_state(engine: Engine, version_id: str, status: str, *, last_chunk_index: int | None = None, error_message: str | None = None) -> None:
    existing = get_ingest_state(engine, version_id)
    if not is_valid_ingest_transition(existing.status if existing else None, status):
        raise RuntimeError(
            f"Invalid ingest_state transition for {version_id}: "
            f"{existing.status if existing else '<none>'} -> {status}"
        )
    sql = text(
        """
        INSERT INTO ingest_state(version_id, status, last_chunk_index, attempt_count)
        VALUES (:version_id, :status, :last_chunk_index, 0)
        ON CONFLICT (version_id) DO UPDATE
          SET status = EXCLUDED.status,
              last_chunk_index = EXCLUDED.last_chunk_index,
              last_step_at = now(),
              error_message = :error_message,
              attempt_count = CASE
                  WHEN EXCLUDED.status = 'discovered' THEN ingest_state.attempt_count + 1
                  ELSE ingest_state.attempt_count
              END,
              updated_at = now()
        """
    )
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "version_id": version_id,
                "status": status,
                "last_chunk_index": last_chunk_index,
                "error_message": error_message,
            },
        )


def upsert_chunks_batch(engine: Engine, rows: List[dict]) -> None:
    """
    Insert chunks in a batch. Uses ON CONFLICT to allow reruns.
    """
    sql = text(
        """
        INSERT INTO chunks(
          chunk_id, version_id, work_id, author_id, chunk_index,
          heading_text, heading_path,
          start_char_offset, end_char_offset,
          text_raw, text_norm,
          word_count, token_count,
          prev_chunk_id, next_chunk_id,
          metadata
        )
        VALUES (
          :chunk_id, :version_id, :work_id, :author_id, :chunk_index,
          :heading_text, :heading_path,
          :start_char_offset, :end_char_offset,
          :text_raw, :text_norm,
          :word_count, :token_count,
          :prev_chunk_id, :next_chunk_id,
          :metadata
        )
        ON CONFLICT (chunk_id) DO UPDATE
          SET text_raw = EXCLUDED.text_raw,
              text_norm = EXCLUDED.text_norm,
              heading_text = EXCLUDED.heading_text,
              heading_path = EXCLUDED.heading_path,
              start_char_offset = EXCLUDED.start_char_offset,
              end_char_offset = EXCLUDED.end_char_offset,
              word_count = EXCLUDED.word_count,
              token_count = EXCLUDED.token_count,
              prev_chunk_id = EXCLUDED.prev_chunk_id,
              next_chunk_id = EXCLUDED.next_chunk_id,
              updated_at = now()
        """
    ).bindparams(bindparam("metadata", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(sql, rows)

def set_chunk_links(engine: Engine, version_id: str) -> None:
    """
    Populate prev/next links after all chunks for a version are inserted.
    This avoids FK violations when batch boundaries split adjacent chunks.
    """
    sql = text(
        """
        UPDATE chunks c
        SET
          prev_chunk_id = (
            SELECT p.chunk_id
            FROM chunks p
            WHERE p.version_id = c.version_id
              AND p.chunk_index = c.chunk_index - 1
          ),
          next_chunk_id = (
            SELECT n.chunk_id
            FROM chunks n
            WHERE n.version_id = c.version_id
              AND n.chunk_index = c.chunk_index + 1
          ),
          updated_at = now()
        WHERE c.version_id = :version_id
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"version_id": version_id})


# ---------------------------
# OpenSearch bulk indexing
# ---------------------------

def os_bulk_index(docs: List[dict]) -> None:
    client = get_opensearch()
    index = settings.OPENSEARCH_INDEX_CHUNKS

    # OpenSearch bulk API expects NDJSON actions
    lines = []
    for d in docs:
        doc_id = d.get("chunk_id")
        lines.append(json.dumps({"index": {"_index": index, "_id": doc_id}}, ensure_ascii=False))
        lines.append(json.dumps(d, ensure_ascii=False))
    payload = "\n".join(lines) + "\n"

    # Use client.bulk to avoid duplicate Content-Type headers
    resp = client.bulk(body=payload)
    if resp.get("errors"):
        # Pull out a small sample of failures
        items = resp.get("items", [])
        failures = []
        for it in items:
            action = it.get("index") or {}
            if "error" in action:
                failures.append(action["error"])
                if len(failures) >= 3:
                    break
        raise RuntimeError(f"OpenSearch bulk indexing had errors. Sample: {failures}")


# ---------------------------
# Qdrant collection + upsert
# ---------------------------

def ensure_qdrant_collection(model: SentenceTransformer, collection_name: str) -> None:
    q = get_qdrant()
    existing = {c.name for c in q.get_collections().collections}
    if collection_name in existing:
        return
    dim = model.get_sentence_embedding_dimension()
    q.create_collection(
        collection_name=collection_name,
        vectors_config={
            "size": dim,
            "distance": "Cosine",
        },
    )


def qdrant_upsert(points: List[dict]) -> None:
    q = get_qdrant()
    q.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)

def qdrant_point_id(chunk_id: str) -> int:
    """
    Qdrant point IDs must be an unsigned int or UUID.
    Use a stable unsigned 64-bit int derived from the chunk_id.
    """
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def build_vector_payload(
    *,
    chunk_id: str,
    chunk_index: int,
    t: DiscoveredText,
    meta: dict | None = None,
) -> dict:
    md = meta or {}
    return {
        "chunk_id": chunk_id,
        "work_id": t.work_id,
        "version_id": t.version_id,
        "author_id": t.author_id,
        "lang": t.lang,
        "is_pri": bool(t.is_pri),
        "chunk_index": chunk_index,
        "period": md.get("period"),
        "region": md.get("region") or [],
        "tags": md.get("tags") or [],
        "version_label": md.get("version_label"),
    }


# ---------------------------
# Runner
# ---------------------------

def resolve_embedding_device(requested: str) -> str:
    requested = (requested or "cpu").lower()
    if requested in ("auto", "cuda"):
        try:
            import torch  # local import to avoid import cost if embeddings disabled
        except Exception as exc:
            LOG.warning("CUDA check failed (%s). Falling back to CPU.", exc)
            return "cpu"
        if torch.cuda.is_available():
            return "cuda"
        if requested == "cuda":
            LOG.warning(
                "EMBEDDING_DEVICE=cuda requested but CUDA is unavailable. "
                "Falling back to CPU. If you expected GPU, use the CUDA image "
                "and ensure NVIDIA drivers + container runtime are installed."
            )
        return "cpu"
    if requested == "cpu":
        return "cpu"
    LOG.warning("Unknown EMBEDDING_DEVICE=%s; falling back to cpu.", requested)
    return "cpu"


def run() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    ingest_settings = {
        k: v for k, v in os.environ.items() if k.startswith("INGEST_")
    }
    ingest_settings_str = ", ".join(
        f"{k}={ingest_settings[k]}" for k in sorted(ingest_settings)
    ) or "none"
    resolved_device = resolve_embedding_device(EMBEDDING_DEVICE) if EMBEDDINGS_ENABLED else "cpu"
    LOG.info(
        "Ingest start: embeddings=%s device=%s (resolved=%s); ingest_settings=%s",
        "enabled" if EMBEDDINGS_ENABLED else "disabled",
        EMBEDDING_DEVICE,
        resolved_device,
        ingest_settings_str,
    )

    corpus_root = Path(os.getenv("CORPUS_ROOT", "")).resolve()
    if not corpus_root.exists():
        raise RuntimeError("CORPUS_ROOT is not set or does not exist inside the container.")

    engine = get_engine()
    ensure_write_index_target(settings.OPENSEARCH_INDEX_CHUNKS)

    curated_tags = _load_curated_tags()
    metadata_by_path, metadata_by_version = load_metadata(corpus_root, curated_tags)

    LOG.info("Discovering texts under %s", corpus_root)
    texts = discover_200_pri_arabic(
        corpus_root,
        target_works=DEFAULT_TARGET_WORKS,
        metadata_by_path=metadata_by_path,
    )
    if not texts:
        raise RuntimeError("No OpenITI-like text files discovered. Check CORPUS_ROOT mount and RELEASE/data layout.")

    LOG.info("Discovered %d texts (target=%d). only_pri=%s langs=%s",
             len(texts), DEFAULT_TARGET_WORKS, DEFAULT_ONLY_PRI, DEFAULT_LANGS)
    LOG.info("Resumable ingest mode: SKIP_EXISTING=%s", SKIP_EXISTING)

    model: SentenceTransformer | None = None
    if EMBEDDINGS_ENABLED:
        LOG.info("Loading embedding model: %s (device=%s)", EMBEDDING_MODEL_ID, resolved_device)
        model = SentenceTransformer(EMBEDDING_MODEL_ID, device=resolved_device)
        ensure_qdrant_collection(model, settings.QDRANT_COLLECTION)

    run_stats = {
        "processed": 0,
        "resumed": 0,
        "skipped_complete": 0,
        "failed": 0,
        "reprocessed": 0,
    }

    # Process each text end-to-end
    for t in tqdm(texts, desc="Ingest versions", unit="version"):
        try:
            meta = metadata_by_path.get(t.repo_path) or metadata_by_version.get(t.abs_path.stem)
            db_version = get_version_row(engine, t.version_id)

            source_lang = normalize_language_tag((meta or {}).get("lang"))
            db_lang = normalize_language_tag((db_version or {}).get("lang"))
            effective_lang = source_lang if source_lang != UNKNOWN_LANGUAGE else db_lang
            if effective_lang == UNKNOWN_LANGUAGE:
                effective_lang = normalize_language_tag(t.lang)
            if effective_lang == UNKNOWN_LANGUAGE:
                LOG.warning("Language metadata missing/unmapped for %s. Using unknown.", t.repo_path)

            db_is_pri = bool((db_version or {}).get("is_pri", False))
            effective_is_pri = _metadata_is_pri(
                status=(meta.get("status") or "") if meta else None,
                version_label=(meta.get("version_label") or "") if meta else None,
                fallback=db_is_pri if db_version is not None else bool(t.is_pri),
            )
            t_effective = DiscoveredText(
                author_id=t.author_id,
                work_id=t.work_id,
                version_id=t.version_id,
                repo_path=t.repo_path,
                abs_path=t.abs_path,
                is_pri=effective_is_pri,
                lang=effective_lang,
            )

            author_name_lat = None
            work_title_ar = None
            work_title_lat = None
            author_meta: dict = {}
            work_meta: dict = {}
            version_meta: dict = {}

            if meta:
                author_name_lat = meta.get("author_lat") or meta.get("author_lat_shuhra")
                work_title_ar = meta.get("work_title_ar")
                work_title_lat = meta.get("work_title_lat")
                author_meta = {
                    "author_lat_shuhra": meta.get("author_lat_shuhra"),
                    "author_lat_full_name": meta.get("author_lat_full_name"),
                }
                work_meta = {
                    "book": meta.get("book"),
                }
                version_meta = {
                    "date_ah": meta.get("date_ah"),
                    "date_ce": meta.get("date_ce"),
                    "period_tag": meta.get("period_tag"),
                    "period": meta.get("period"),
                    "region": meta.get("region"),
                    "tags": meta.get("tags"),
                    "status": meta.get("status"),
                    "version_label": meta.get("version_label"),
                    "local_path": meta.get("local_path"),
                    "ed_info": meta.get("ed_info"),
                    "source_id": meta.get("id"),
                }

            # Basic upserts (now metadata-aware)
            upsert_author(
                engine,
                t.author_id,
                name_ar=meta.get("author_ar") if meta else None,
                name_latn=author_name_lat,
                metadata=author_meta,
            )
            upsert_work(
                engine,
                t.work_id,
                t.author_id,
                title_ar=work_title_ar,
                title_latn=work_title_lat,
                metadata=work_meta,
            )
            # Ensure the version exists before any ingest_state updates (FK constraint).
            upsert_version(engine, t_effective, checksum=None, word_count=None, char_count=None, metadata=version_meta)
            existing_state = get_ingest_state(engine, t_effective.version_id)
            decision = decide_ingest_behavior(
                existing_state,
                skip_existing=SKIP_EXISTING,
                embeddings_enabled=EMBEDDINGS_ENABLED,
            )

            if decision.action == "skip_complete":
                run_stats["skipped_complete"] += 1
                LOG.info("Skipping version_id=%s (%s)", t_effective.version_id, decision.reason)
                continue

            if decision.action == "resume":
                run_stats["resumed"] += 1
            else:
                run_stats["processed"] += 1
                if existing_state is not None:
                    run_stats["reprocessed"] += 1

            if decision.start_chunk_index == 0 or (existing_state is not None and existing_state.status == "failed"):
                set_ingest_state(engine, t.version_id, "discovered")
            else:
                LOG.info(
                    "Resuming version_id=%s from chunk_index=%d (%s)",
                    t_effective.version_id,
                    decision.start_chunk_index,
                    decision.reason,
                )
            checkpoint_bm25 = not (
                decision.action == "resume"
                and existing_state is not None
                and existing_state.status == "embedded"
            )

            raw = read_text_file(t.abs_path)
            checksum = sha256_file(t.abs_path)

            # quick stats
            raw_compact = re.sub(r"\s+", " ", raw).strip()
            word_count = len(raw_compact.split(" ")) if raw_compact else 0
            char_count = len(raw)

            upsert_version(
                engine,
                t_effective,
                checksum=checksum,
                word_count=word_count,
                char_count=char_count,
                metadata=version_meta,
            )
            if decision.start_chunk_index == 0:
                set_ingest_state(engine, t.version_id, "parsed")

            chunk_plan = build_chunk_plan(
                raw,
                target_words=CHUNK_TARGET_WORDS,
                overlap_words=CHUNK_MAX_OVERLAP_WORDS,
            )
            if not chunk_plan:
                set_ingest_state(engine, t.version_id, "failed", error_message="empty text after normalization")
                continue

            chunk_rows: List[dict] = []
            os_docs: List[dict] = []
            os_meta = meta or {}
            os_author_name_lat = os_meta.get("author_lat") or os_meta.get("author_lat_shuhra")

            # Create chunk rows in memory, then batch insert/index
            chunks_for_vectors: List[Tuple[str, str, dict]] = []  # (chunk_id, text_norm, payload)

            for planned_chunk in chunk_plan:
                if planned_chunk.chunk_index < decision.start_chunk_index:
                    continue
                chunk_id = f"{t.version_id}::{planned_chunk.chunk_index}"

                row = {
                    "chunk_id": chunk_id,
                    "version_id": t.version_id,
                    "work_id": t.work_id,
                    "author_id": t.author_id,
                    "chunk_index": planned_chunk.chunk_index,
                    "heading_text": planned_chunk.heading_text,
                    "heading_path": planned_chunk.heading_path,
                    "start_char_offset": planned_chunk.start_char_offset,
                    "end_char_offset": planned_chunk.end_char_offset,
                    "text_raw": planned_chunk.text_raw,
                    "text_norm": planned_chunk.text_norm,
                    "word_count": planned_chunk.word_count,
                    "token_count": None,
                    "prev_chunk_id": None,
                    "next_chunk_id": None,
                    "metadata": "{}",
                }

                chunk_rows.append(row)

                os_docs.append(
                    {
                        "chunk_id": chunk_id,
                        "work_id": t.work_id,
                        "version_id": t.version_id,
                        "author_id": t.author_id,
                        "lang": t_effective.lang,
                        "is_pri": t_effective.is_pri,
                        "title": None,
                        "content": planned_chunk.text_norm,
                        "author_name_ar": os_meta.get("author_ar"),
                        "author_name_lat": os_author_name_lat,
                        "work_title_ar": os_meta.get("work_title_ar"),
                        "work_title_lat": os_meta.get("work_title_lat"),
                        "date_ah": os_meta.get("date_ah"),
                        "date_ce": os_meta.get("date_ce"),
                        "period": os_meta.get("period"),
                        "period_tag": os_meta.get("period_tag"),
                        "region": os_meta.get("region") or [],
                        "tags": os_meta.get("tags") or [],
                        "version_label": os_meta.get("version_label"),
                        "type": "Passage",
                    }
                )

                if EMBEDDINGS_ENABLED and model is not None:
                    payload = build_vector_payload(
                        chunk_id=chunk_id,
                        chunk_index=planned_chunk.chunk_index,
                        t=t_effective,
                        meta=os_meta,
                    )
                    chunks_for_vectors.append((chunk_id, planned_chunk.text_norm, payload))

                # batch flush
                if len(chunk_rows) >= OS_BULK_BATCH:
                    upsert_chunks_batch(engine, chunk_rows)
                    os_bulk_index(os_docs)
                    if checkpoint_bm25:
                        set_ingest_state(engine, t.version_id, "indexed_bm25", last_chunk_index=chunk_rows[-1]["chunk_index"])

                    if EMBEDDINGS_ENABLED and model is not None and chunks_for_vectors:
                        _embed_and_upsert(model, chunks_for_vectors)
                        set_ingest_state(engine, t.version_id, "embedded", last_chunk_index=chunk_rows[-1]["chunk_index"])
                        chunks_for_vectors.clear()

                    chunk_rows.clear()
                    os_docs.clear()

            # final flush
            if chunk_rows:
                upsert_chunks_batch(engine, chunk_rows)
                os_bulk_index(os_docs)
                if checkpoint_bm25:
                    set_ingest_state(engine, t.version_id, "indexed_bm25", last_chunk_index=chunk_rows[-1]["chunk_index"])

                if EMBEDDINGS_ENABLED and model is not None and chunks_for_vectors:
                    _embed_and_upsert(model, chunks_for_vectors)
                    set_ingest_state(engine, t.version_id, "embedded", last_chunk_index=chunk_rows[-1]["chunk_index"])

            # Populate prev/next links after all chunks for this version exist.
            set_chunk_links(engine, t.version_id)
            set_ingest_state(engine, t.version_id, "complete")

        except Exception as e:
            LOG.exception("Failed ingest for version_id=%s path=%s", t.version_id, t.repo_path)
            set_ingest_state(engine, t.version_id, "failed", error_message=str(e))
            run_stats["failed"] += 1

    LOG.info(
        "Ingest run complete. processed=%d resumed=%d skipped_complete=%d reprocessed=%d failed=%d",
        run_stats["processed"],
        run_stats["resumed"],
        run_stats["skipped_complete"],
        run_stats["reprocessed"],
        run_stats["failed"],
    )


def _embed_and_upsert(model: SentenceTransformer, chunks_for_vectors: List[Tuple[str, str, dict]]) -> None:
    """
    Embed a batch of chunk texts and upsert into Qdrant.
    """
    texts = [t for _, t, _ in chunks_for_vectors]
    ids = [cid for cid, _, _ in chunks_for_vectors]
    payloads = [p for _, _, p in chunks_for_vectors]

    vectors = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    points = []
    for i, cid in enumerate(ids):
        points.append(
            {
                "id": qdrant_point_id(cid),
                "vector": vectors[i].tolist(),
                "payload": payloads[i],
            }
        )
    qdrant_upsert(points)


if __name__ == "__main__":
    run()

