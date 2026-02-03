from __future__ import annotations

import os
import re
import sys
import json
import time
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple, Dict

from tqdm import tqdm
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from ..db import get_engine
from ..settings import settings
from ..clients.opensearch_client import get_opensearch
from ..clients.qdrant_client import get_qdrant

# Embeddings
from sentence_transformers import SentenceTransformer


LOG = logging.getLogger("openiti.ingest")


# ---------------------------
# Config
# ---------------------------

DEFAULT_TARGET_WORKS = int(os.getenv("INGEST_WORK_LIMIT", "200") or "200")
DEFAULT_ONLY_PRI = os.getenv("INGEST_ONLY_PRI", "true").lower() in ("1", "true", "yes")
DEFAULT_LANGS = os.getenv("INGEST_LANGS", "ara").split(",")  # for this runner we expect ara
CHUNK_TARGET_WORDS = int(os.getenv("CHUNK_TARGET_WORDS", "300") or "300")
CHUNK_MAX_OVERLAP_WORDS = int(os.getenv("CHUNK_MAX_OVERLAP_WORDS", "0") or "0")

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


# ---------------------------
# Normalization (Arabic-script)
# ---------------------------

AR_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670]")  # harakat + superscript alef
TATWEEL_RE = re.compile(r"\u0640")  # ـ

# conservative character normalizations
CHAR_MAP = str.maketrans({
    "ٱ": "ا",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ى": "ي",
    "ة": "ه",
    "ؤ": "و",
    "ئ": "ي",
    # Persian variants commonly present in Arabic-script corpora
    "ك": "ک",
    "ي": "ی",
})

def normalize_arabic_script(s: str) -> str:
    s = TATWEEL_RE.sub("", s)
    s = AR_DIACRITICS_RE.sub("", s)
    s = s.translate(CHAR_MAP)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


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
    lang: str  # 'ara' for this runner


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


def discover_200_pri_arabic(corpus_root: Path, target_works: int) -> List[DiscoveredText]:
    """
    Discover texts by walking data/ and selecting up to target_works PRI versions in Arabic.
    """
    # Group by work directory: data/<author>/<work>/
    files_by_workdir: Dict[Path, List[Path]] = {}
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

    pri_files = choose_pri_versions(files_by_workdir) if DEFAULT_ONLY_PRI else [f for fs in files_by_workdir.values() for f in fs]

    discovered: List[DiscoveredText] = []
    for fp in pri_files:
        author_id, work_id, version_id, repo_rel = infer_ids_from_path(corpus_root, fp)

        # crude Arabic filter: allow only if requested langs include ara
        lang = "ara"
        if "ara" not in DEFAULT_LANGS:
            continue

        # Mark PRI by filename heuristic or single-file selection
        is_pri = True if (("PRI" in fp.name) or ("pri" in fp.name)) else DEFAULT_ONLY_PRI

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

def upsert_author(engine: Engine, author_id: str) -> None:
    sql = text(
        """
        INSERT INTO authors(author_id, metadata)
        VALUES (:author_id, '{}'::jsonb)
        ON CONFLICT (author_id) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"author_id": author_id})


def upsert_work(engine: Engine, work_id: str, author_id: str) -> None:
    sql = text(
        """
        INSERT INTO works(work_id, author_id, metadata)
        VALUES (:work_id, :author_id, '{}'::jsonb)
        ON CONFLICT (work_id) DO UPDATE
          SET author_id = EXCLUDED.author_id
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, {"work_id": work_id, "author_id": author_id})


def upsert_version(engine: Engine, t: DiscoveredText, checksum: str | None, word_count: int | None, char_count: int | None) -> None:
    sql = text(
        """
        INSERT INTO versions(version_id, work_id, is_pri, lang, repo_path, checksum_sha256, word_count, char_count, metadata)
        VALUES (:version_id, :work_id, :is_pri, :lang, :repo_path, :checksum, :word_count, :char_count, '{}'::jsonb)
        ON CONFLICT (version_id) DO UPDATE
          SET work_id = EXCLUDED.work_id,
              is_pri = EXCLUDED.is_pri,
              lang = EXCLUDED.lang,
              repo_path = EXCLUDED.repo_path,
              checksum_sha256 = EXCLUDED.checksum_sha256,
              word_count = EXCLUDED.word_count,
              char_count = EXCLUDED.char_count
        """
    )
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
            },
        )


def set_ingest_state(engine: Engine, version_id: str, status: str, *, last_chunk_index: int | None = None, error_message: str | None = None) -> None:
    sql = text(
        """
        INSERT INTO ingest_state(version_id, status, last_chunk_index, attempt_count)
        VALUES (:version_id, :status, :last_chunk_index, 0)
        ON CONFLICT (version_id) DO UPDATE
          SET status = EXCLUDED.status,
              last_chunk_index = EXCLUDED.last_chunk_index,
              last_step_at = now(),
              error_message = :error_message,
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
              prev_chunk_id = EXCLUDED.prev_chunk_id,
              next_chunk_id = EXCLUDED.next_chunk_id,
              updated_at = now()
        """
    ).bindparams(bindparam("metadata", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(sql, rows)


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

    resp = client.transport.perform_request(
        method="POST",
        url="/_bulk",
        body=payload,
        headers={"Content-Type": "application/x-ndjson"},
    )
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

    LOG.info("Discovering texts under %s", corpus_root)
    texts = discover_200_pri_arabic(corpus_root, target_works=DEFAULT_TARGET_WORKS)
    if not texts:
        raise RuntimeError("No OpenITI-like text files discovered. Check CORPUS_ROOT mount and RELEASE/data layout.")

    LOG.info("Discovered %d texts (target=%d). only_pri=%s langs=%s",
             len(texts), DEFAULT_TARGET_WORKS, DEFAULT_ONLY_PRI, DEFAULT_LANGS)

    model: SentenceTransformer | None = None
    if EMBEDDINGS_ENABLED:
        LOG.info("Loading embedding model: %s (device=%s)", EMBEDDING_MODEL_ID, resolved_device)
        model = SentenceTransformer(EMBEDDING_MODEL_ID, device=resolved_device)
        ensure_qdrant_collection(model, settings.QDRANT_COLLECTION)

    # Process each text end-to-end
    for t in tqdm(texts, desc="Ingest versions", unit="version"):
        try:
            # Basic upserts (metadata-heavy ingestion comes later)
            upsert_author(engine, t.author_id)
            upsert_work(engine, t.work_id, t.author_id)
            # Ensure the version exists before any ingest_state updates (FK constraint).
            upsert_version(engine, t, checksum=None, word_count=None, char_count=None)
            set_ingest_state(engine, t.version_id, "discovered")

            raw = read_text_file(t.abs_path)
            checksum = sha256_file(t.abs_path)

            # quick stats
            raw_compact = re.sub(r"\s+", " ", raw).strip()
            word_count = len(raw_compact.split(" ")) if raw_compact else 0
            char_count = len(raw)

            upsert_version(engine, t, checksum=checksum, word_count=word_count, char_count=char_count)
            set_ingest_state(engine, t.version_id, "parsed")

            heading_text, heading_path = extract_heading_context(raw)

            # normalize + chunk
            norm = normalize_arabic_script(raw)
            words = norm.split(" ") if norm else []
            if not words:
                set_ingest_state(engine, t.version_id, "failed", error_message="empty text after normalization")
                continue

            chunk_rows: List[dict] = []
            os_docs: List[dict] = []

            # Create chunk rows in memory, then batch insert/index
            last_chunk_id = None
            chunks_for_vectors: List[Tuple[str, str, dict]] = []  # (chunk_id, text_norm, payload)

            for chunk_index, start_word, wslice in chunk_words(words, CHUNK_TARGET_WORDS, CHUNK_MAX_OVERLAP_WORDS):
                chunk_id = f"{t.version_id}::{chunk_index}"
                text_norm = " ".join(wslice).strip()
                # for display, take a slice from raw by approximate proportion (fallback)
                text_raw = text_norm  # MVP: later replace with true raw slicing

                row = {
                    "chunk_id": chunk_id,
                    "version_id": t.version_id,
                    "work_id": t.work_id,
                    "author_id": t.author_id,
                    "chunk_index": chunk_index,
                    "heading_text": heading_text,
                    "heading_path": heading_path,
                    "start_char_offset": None,
                    "end_char_offset": None,
                    "text_raw": text_raw,
                    "text_norm": text_norm,
                    "word_count": len(wslice),
                    "token_count": None,
                    "prev_chunk_id": last_chunk_id,
                    "next_chunk_id": None,
                    "metadata": "{}",
                }

                # update previous chunk's next pointer (in memory; will persist later)
                if last_chunk_id is not None:
                    # patch the prior row's next_chunk_id
                    chunk_rows[-1]["next_chunk_id"] = chunk_id

                chunk_rows.append(row)
                last_chunk_id = chunk_id

                os_docs.append(
                    {
                        "chunk_id": chunk_id,
                        "work_id": t.work_id,
                        "version_id": t.version_id,
                        "author_id": t.author_id,
                        "lang": t.lang,
                        "is_pri": t.is_pri,
                        "title": None,
                        "content": text_norm,
                    }
                )

                if EMBEDDINGS_ENABLED and model is not None:
                    payload = {
                        "chunk_id": chunk_id,
                        "work_id": t.work_id,
                        "version_id": t.version_id,
                        "author_id": t.author_id,
                        "lang": t.lang,
                        "is_pri": bool(t.is_pri),
                        "chunk_index": chunk_index,
                    }
                    chunks_for_vectors.append((chunk_id, text_norm, payload))

                # batch flush
                if len(chunk_rows) >= OS_BULK_BATCH:
                    upsert_chunks_batch(engine, chunk_rows)
                    os_bulk_index(os_docs)
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
                set_ingest_state(engine, t.version_id, "indexed_bm25", last_chunk_index=chunk_rows[-1]["chunk_index"])

                if EMBEDDINGS_ENABLED and model is not None and chunks_for_vectors:
                    _embed_and_upsert(model, chunks_for_vectors)
                    set_ingest_state(engine, t.version_id, "embedded", last_chunk_index=chunk_rows[-1]["chunk_index"])

            set_ingest_state(engine, t.version_id, "complete")

        except Exception as e:
            LOG.exception("Failed ingest for version_id=%s path=%s", t.version_id, t.repo_path)
            set_ingest_state(engine, t.version_id, "failed", error_message=str(e))

    LOG.info("Ingest run complete.")


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
                "id": cid,  # stable id in qdrant
                "vector": vectors[i].tolist(),
                "payload": payloads[i],
            }
        )
    qdrant_upsert(points)


if __name__ == "__main__":
    run()
