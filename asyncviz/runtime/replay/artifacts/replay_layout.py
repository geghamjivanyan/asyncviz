"""On-disk layout constants for the AsyncViz replay artifact bundle.

A replay bundle is a *directory* (with a ``.avz`` extension by
convention) shaped like:

  session.avz/
  ├── manifest.json                  # canonical entry — version + chunk
  │                                  #   inventory + integrity hashes.
  ├── meta/
  │   ├── runtime.json               # runtime_id, target spec, timings.
  │   ├── packaging.json             # asyncviz packaging diagnostics.
  │   └── recorder.json              # recorder self-metrics.
  ├── events/
  │   ├── chunk-00000.jsonl          # NDJSON, one frame per line.
  │   ├── chunk-00001.jsonl(.gz)
  │   └── ...
  ├── snapshots/
  │   ├── runtime-final.json         # post-run RuntimeStateSnapshot.
  │   └── warnings-final.json        # blocking-warning emitter snapshot.
  └── INCOMPLETE                     # tombstone — present until the
                                      #   writer cleanly finalizes.

The directory shape (vs. tar.gz) is deliberate — it's easy to inspect
manually, supports incremental writes, and a future task can wrap it
in a tarball without touching this module.
"""

from __future__ import annotations

#: Bumped when the on-disk schema changes in a backward-incompatible
#: way. Readers refuse to open bundles whose schema version exceeds
#: the version they know about.
ARTIFACT_SCHEMA_VERSION: int = 1

#: Conventional suffix for replay bundle directories.
BUNDLE_EXTENSION: str = ".avz"

MANIFEST_FILENAME: str = "manifest.json"

META_DIRECTORY: str = "meta"
CHUNK_DIRECTORY: str = "events"
SNAPSHOT_DIRECTORY: str = "snapshots"

#: Marker file written at bundle-open time + deleted on clean finalize.
#: A reader sees ``INCOMPLETE`` to know the bundle wasn't closed.
INCOMPLETE_MARKER: str = "INCOMPLETE"

#: Snapshot file conventions — kept here so the writer + reader can't
#: disagree on the file name.
RUNTIME_SNAPSHOT_FILENAME: str = "runtime-final.json"
WARNINGS_SNAPSHOT_FILENAME: str = "warnings-final.json"

#: Meta files written under ``meta/``.
RUNTIME_META_FILENAME: str = "runtime.json"
PACKAGING_META_FILENAME: str = "packaging.json"
RECORDER_META_FILENAME: str = "recorder.json"


def build_chunk_name(chunk_index: int, *, compressed: bool) -> str:
    """Format the on-disk name for chunk ``chunk_index``.

    Indices are zero-padded to five digits so lexical sort matches
    numerical sort up to 100k chunks — well beyond any expected
    runtime length.
    """
    suffix = ".jsonl.gz" if compressed else ".jsonl"
    return f"chunk-{chunk_index:05d}{suffix}"


def runtime_meta_filename() -> str:
    """Public accessor — used by the writer + the validator."""
    return RUNTIME_META_FILENAME
