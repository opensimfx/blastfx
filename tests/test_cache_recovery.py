import json

from blastfx.core.cache_layout import (
    COMPLETE_MARKER,
    EXPECTED_MARKER,
    GENERATION_MARKER,
    recover_generation,
)


def _make_generation(root, *, baked=False, with_files=True, state_hash="abc"):
    generation = root / "gen123"
    generation.mkdir(parents=True)
    (root / GENERATION_MARKER).write_text("gen123", encoding="utf-8")
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
    root = tmp_path / "blast_x"
    root.mkdir()
    (root / GENERATION_MARKER).write_text("../escape", encoding="utf-8")
    assert recover_generation(root) == "invalidated: broken generation contract"
    assert not root.exists()


def test_missing_generation_dir_invalidates(tmp_path):
    root = tmp_path / "blast_x"
    root.mkdir()
    (root / GENERATION_MARKER).write_text("gone", encoding="utf-8")
    assert recover_generation(root) == "invalidated: broken generation contract"
    assert not root.exists()


def test_stale_job_dirs_removed_and_valid_cache_kept(tmp_path):
    root = tmp_path / "blast_x"
    generation = _make_generation(root, baked=True)
    job_dir = generation / "job" / "job1"
    job_dir.mkdir(parents=True)
    (job_dir / "scene.blend").write_bytes(b"z" * 16)
    note = recover_generation(root)
    assert note == "removed 1 stale job dir(s)"
    assert not job_dir.exists()
    assert (generation / EXPECTED_MARKER).exists()
    assert (generation / COMPLETE_MARKER).exists()
    assert (generation / "config" / "data" / "density_0001.vdb").exists()


def test_baked_marker_without_files_is_healed(tmp_path):
    root = tmp_path / "blast_x"
    generation = _make_generation(root, baked=True, with_files=False)
    note = recover_generation(root)
    assert note == "cleared baked marker without cache files"
    assert not (generation / COMPLETE_MARKER).exists()
    # Partial/empty generations are not destroyed; a rebake reuses the contract.
    assert root.exists()


def test_consistent_baked_generation_is_left_alone(tmp_path):
    root = tmp_path / "blast_x"
    _make_generation(root, baked=True)
    assert recover_generation(root) is None


def test_inconsistent_markers_invalidate(tmp_path):
    root = tmp_path / "blast_x"
    generation = _make_generation(root, baked=True, state_hash="abc")
    (generation / COMPLETE_MARKER).write_text(
        json.dumps({"state_hash": "other"}), encoding="utf-8"
    )
    assert recover_generation(root) == "invalidated: inconsistent cache markers"
    assert not root.exists()


def test_unreadable_markers_invalidate(tmp_path):
    root = tmp_path / "blast_x"
    generation = _make_generation(root, baked=True)
    (generation / COMPLETE_MARKER).write_text("not json", encoding="utf-8")
    assert recover_generation(root) == "invalidated: unreadable cache markers"
    assert not root.exists()
