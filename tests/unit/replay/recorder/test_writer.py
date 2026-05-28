from __future__ import annotations

import gzip
from pathlib import Path

from asyncviz.runtime.replay.artifacts.replay_layout import CHUNK_DIRECTORY
from asyncviz.runtime.replay.recorder.replay_chunking import ChunkPolicy
from asyncviz.runtime.replay.recorder.replay_compression import CompressionMode
from asyncviz.runtime.replay.recorder.replay_writer import ReplayWriter


def _line(seq: int) -> bytes:
    return f'{{"seq":{seq}}}\n'.encode()


def test_writer_emits_one_chunk_per_threshold(tmp_path: Path) -> None:
    writer = ReplayWriter(
        bundle_dir=tmp_path,
        compression=CompressionMode.NONE,
        chunk_policy=ChunkPolicy(max_events=2, max_bytes=0),
    )
    for seq in range(1, 6):
        writer.write_record(sequence=seq, payload=_line(seq))
    writer.close()
    chunks = writer.finalized_chunks
    # 5 events, max 2 per chunk → 3 chunks (sizes 2, 2, 1).
    assert len(chunks) == 3
    assert [c.event_count for c in chunks] == [2, 2, 1]
    assert chunks[0].sequence_start == 1
    assert chunks[-1].sequence_end == 5


def test_writer_skips_empty_close(tmp_path: Path) -> None:
    writer = ReplayWriter(
        bundle_dir=tmp_path,
        compression=CompressionMode.NONE,
        chunk_policy=ChunkPolicy(max_events=10, max_bytes=0),
    )
    writer.close()  # no records written
    assert writer.finalized_chunks == ()
    chunk_dir = tmp_path / CHUNK_DIRECTORY
    if chunk_dir.exists():
        assert not list(chunk_dir.glob("chunk-*.jsonl"))


def test_writer_gzip_creates_readable_chunks(tmp_path: Path) -> None:
    writer = ReplayWriter(
        bundle_dir=tmp_path,
        compression=CompressionMode.GZIP,
        chunk_policy=ChunkPolicy(max_events=10, max_bytes=0),
    )
    for seq in range(1, 4):
        writer.write_record(sequence=seq, payload=_line(seq))
    writer.close()
    chunks = writer.finalized_chunks
    assert len(chunks) == 1
    path = tmp_path / chunks[0].file
    assert path.suffix == ".gz"
    with gzip.open(path, "rt") as fh:
        lines = fh.read().splitlines()
    assert len(lines) == 3
    assert '"seq":1' in lines[0]


def test_writer_records_sha256(tmp_path: Path) -> None:
    writer = ReplayWriter(
        bundle_dir=tmp_path,
        compression=CompressionMode.NONE,
        chunk_policy=ChunkPolicy(max_events=10, max_bytes=0),
    )
    writer.write_record(sequence=1, payload=_line(1))
    writer.close()
    chunk = writer.finalized_chunks[0]
    assert len(chunk.sha256) == 64  # SHA-256 hex digest
    assert chunk.compressed_bytes > 0
