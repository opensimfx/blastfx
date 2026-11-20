import json

import os

import pytest

from blastfx.core.cache_layout import (
    COMPLETE_MARKER,
    EXPECTED_MARKER,
    GENERATION_MARKER,
    blast_dir,
    has_blastfx_marker,
    is_valid_blast_id,
    recover_generation,
    remove_blast_dir,
)

def _symlink(target, link):
    """Windows only allows symlinks with admin rights or Developer Mode; skip there instead of failing."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")


BLAST = "a1b2c3d4"                  # controller.new_blast_id(): 8 hex characters
GEN = "0123456789abcdef" * 2        # uuid4().hex
JOB = "fedcba9876543210" * 2


def _make_generation(root, *, baked=False, with_files=True, state_hash="abc"):
    generation = root / GEN
    generation.mkdir(parents=True)
    (root / GENERATION_MARKER).write_text(GEN, encoding="utf-8")
    (generation / EXPECTED_MARKER).write_text(
        json.dumps({"state_hash": state_hash, "frame_start": 1, "frame_end": 10}),
        encoding="utf-8",
    )
    if baked:
        (generation / COMPLETE_MARKER).write_text(
            json.dumps({"state_hash": state_hash}), encoding="utf-8"
        )
    if with_files:
        (generation / "config" / "data").mkdir(parents=True)
        (generation / "config" / "data" / "density_0001.vdb").write_bytes(b"x" * 32)
    return generation


def test_missing_root_is_a_no_op(tmp_path):
    assert recover_generation(tmp_path / "nope") is None


def test_broken_generation_marker_invalidates(tmp_path):
    root = tmp_path / BLAST
    root.mkdir()
    (root / GENERATION_MARKER).write_text("../escape", encoding="utf-8")
    assert recover_generation(root) == "invalidated: broken generation contract"
    assert not root.exists()


def test_missing_generation_dir_invalidates(tmp_path):
    root = tmp_path / BLAST
    root.mkdir()
    (root / GENERATION_MARKER).write_text("f" * 32, encoding="utf-8")
    assert recover_generation(root) == "invalidated: broken generation contract"
    assert not root.exists()


def test_stale_job_dirs_removed_and_valid_cache_kept(tmp_path):
    root = tmp_path / BLAST
    generation = _make_generation(root, baked=True)
    job_dir = generation / "job" / JOB
    job_dir.mkdir(parents=True)
    (job_dir / "scene.blend").write_bytes(b"z" * 16)
    note = recover_generation(root)
    assert note == "removed 1 stale job dir(s)"
    assert not job_dir.exists()
    assert (generation / EXPECTED_MARKER).exists()
    assert (generation / COMPLETE_MARKER).exists()
    assert (generation / "config" / "data" / "density_0001.vdb").exists()


def test_baked_marker_without_files_is_healed(tmp_path):
    root = tmp_path / BLAST
    generation = _make_generation(root, baked=True, with_files=False)
    note = recover_generation(root)
    assert note == "cleared baked marker without cache files"
    assert not (generation / COMPLETE_MARKER).exists()
    # Partial/empty generations are not destroyed; a rebake reuses the contract.
    assert root.exists()


def test_consistent_baked_generation_is_left_alone(tmp_path):
    root = tmp_path / BLAST
    _make_generation(root, baked=True)
    assert recover_generation(root) is None


def test_inconsistent_markers_invalidate(tmp_path):
    root = tmp_path / BLAST
    generation = _make_generation(root, baked=True, state_hash="abc")
    (generation / COMPLETE_MARKER).write_text(
        json.dumps({"state_hash": "other"}), encoding="utf-8"
    )
    assert recover_generation(root) == "invalidated: inconsistent cache markers"
    assert not root.exists()


def test_unreadable_markers_invalidate(tmp_path):
    root = tmp_path / BLAST
    generation = _make_generation(root, baked=True)
    (generation / COMPLETE_MARKER).write_text("not json", encoding="utf-8")
    assert recover_generation(root) == "invalidated: unreadable cache markers"
    assert not root.exists()


# ------------------------------------------------------------------ untrusted IDs (a .blend is untrusted input)
@pytest.mark.parametrize("bad", ["..", ".", "", "/", "/etc", "../../x", "A1B2C3D4", "a1b2c3d", "a1b2c3d4e",
                                 "a1b2/c3d", "a1b2c3d4/..", "g1b2c3d4", None, 12345678])
def test_only_generated_ids_are_accepted(tmp_path, bad):
    assert not is_valid_blast_id(bad)
    with pytest.raises(ValueError):
        blast_dir(tmp_path, bad)


def test_blast_dir_stays_inside_the_root(tmp_path):
    assert blast_dir(tmp_path, BLAST) == tmp_path / BLAST
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / GENERATION_MARKER).write_text(GEN, encoding="utf-8")
    root = tmp_path / "cache"
    root.mkdir()
    _symlink(outside, root / BLAST)                 # a symlinked blast folder points outside: refused
    with pytest.raises(ValueError):
        blast_dir(root, BLAST)


def test_recovery_never_deletes_a_folder_without_a_marker(tmp_path):
    victim = tmp_path / BLAST
    (victim / "work").mkdir(parents=True)
    (victim / "work" / "thesis.txt").write_text("keep me", encoding="utf-8")
    assert recover_generation(victim) is None
    assert (victim / "work" / "thesis.txt").exists()
    assert not remove_blast_dir(victim) and victim.exists()


def test_recovery_ignores_folders_not_named_like_a_blast(tmp_path):
    other = tmp_path / "Documents"
    other.mkdir()
    (other / GENERATION_MARKER).write_text("broken", encoding="utf-8")   # even with a marker
    assert recover_generation(other) is None and other.exists()
    assert not remove_blast_dir(other)


def test_generation_marker_cannot_point_outside(tmp_path):
    root = tmp_path / BLAST
    root.mkdir()
    sibling = tmp_path / "job"
    (sibling / JOB).mkdir(parents=True)
    (root / GENERATION_MARKER).write_text("..", encoding="utf-8")   # "../job/<hex>" must not be cleaned
    assert recover_generation(root) == "invalidated: broken generation contract"
    assert (sibling / JOB).exists()


def test_symlinked_cache_folder_is_not_deleted(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / GENERATION_MARKER).write_text("broken", encoding="utf-8")
    link = tmp_path / BLAST
    _symlink(target, link)
    assert recover_generation(link) is None
    assert not remove_blast_dir(link)
    assert target.exists()


def test_only_bake_snapshot_folders_are_cleaned(tmp_path):
    root = tmp_path / BLAST
    generation = _make_generation(root, baked=True)
    keep = generation / "job" / "notes"
    keep.mkdir(parents=True)
    assert recover_generation(root) is None
    assert keep.exists()


def test_interrupted_bake_still_counts_as_blastfx(tmp_path):
    # the manifest is written before the root marker; a crash in between must stay recognisable
    root = tmp_path / BLAST
    (root / GEN).mkdir(parents=True)
    (root / GEN / EXPECTED_MARKER).write_text("{}", encoding="utf-8")
    assert has_blastfx_marker(root)
    assert remove_blast_dir(root) and not root.exists()
