"""
Tests for Git Mode per-packet commit granularity (REV-004).

Acceptance Criteria:
- AC-REV-004-1: Two source packets → exactly two new git commits.
- AC-REV-004-2: One source packet → exactly one new commit with only that packet's changes.
- AC-REV-004-3: Commit subject matches schema.
- AC-REV-004-4: Commit body includes queue_ids in deterministic lexical order.
- AC-REV-004-5: Failed commit/write → no partial canonical mutations (atomicity).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mycelium.git_mode import (
    GitModeError,
    PacketPromotion,
    apply_git_mode_promotions,
    build_commit_body,
    build_commit_subject,
    commit_packet_promotion,
)


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    # Initial commit
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


def _get_log(path: Path, n: int = 10) -> list[str]:
    """Get the last n commit subjects."""
    result = subprocess.run(
        ["git", "log", f"-{n}", "--format=%s"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def _get_commit_body(path: Path, ref: str = "HEAD") -> str:
    """Get the body of a specific commit."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%b", ref],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _count_commits(path: Path) -> int:
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return int(result.stdout.strip())


# ---------------------------------------------------------------------------
# build_commit_subject
# ---------------------------------------------------------------------------

class TestBuildCommitSubject:

    def test_basic_subject(self):
        subject = build_commit_subject("pkt-001", "src-abc", ["run-1"])
        assert subject == "graduate packet=pkt-001 source=src-abc run_ids=run-1"

    def test_multiple_run_ids_sorted(self):
        subject = build_commit_subject("pkt-002", "src-xyz", ["run-3", "run-1", "run-2"])
        assert subject == "graduate packet=pkt-002 source=src-xyz run_ids=run-1,run-2,run-3"

    def test_schema_format(self):
        subject = build_commit_subject("p", "s", ["r"])
        assert subject.startswith("graduate packet=")
        assert "source=" in subject
        assert "run_ids=" in subject


# ---------------------------------------------------------------------------
# build_commit_body
# ---------------------------------------------------------------------------

class TestBuildCommitBody:

    def test_sorted_queue_ids(self):
        body = build_commit_body(["q-3", "q-1", "q-2"])
        lines = body.splitlines()
        assert lines[0] == "Applied queue items:"
        assert lines[1].strip() == "- q-1"
        assert lines[2].strip() == "- q-2"
        assert lines[3].strip() == "- q-3"

    def test_single_queue_id(self):
        body = build_commit_body(["q-only"])
        assert "q-only" in body


# ---------------------------------------------------------------------------
# AC-REV-004-1: Two packets → two commits
# ---------------------------------------------------------------------------

class TestTwoPacketsTwoCommits:

    def test_two_packets_produce_two_commits(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        initial_count = _count_commits(tmp_path)

        # Create files for packet 1
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "note-a.md").write_text("# Note A\n")

        pkt1 = PacketPromotion(
            packet_id="pkt-001",
            source_id="src-alpha",
            run_ids=["run-1"],
            queue_ids=["q-a"],
            promoted_paths=["Sources/note-a.md"],
        )
        commit_packet_promotion(tmp_path, pkt1)

        # Create files for packet 2
        (tmp_path / "Sources" / "note-b.md").write_text("# Note B\n")

        pkt2 = PacketPromotion(
            packet_id="pkt-002",
            source_id="src-beta",
            run_ids=["run-2"],
            queue_ids=["q-b"],
            promoted_paths=["Sources/note-b.md"],
        )
        commit_packet_promotion(tmp_path, pkt2)

        new_count = _count_commits(tmp_path)
        assert new_count == initial_count + 2


# ---------------------------------------------------------------------------
# AC-REV-004-2: One packet → one commit with only that packet's diff
# ---------------------------------------------------------------------------

class TestOnePacketOneCommit:

    def test_single_packet_single_commit(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        initial_count = _count_commits(tmp_path)

        (tmp_path / "Claims").mkdir()
        (tmp_path / "Claims" / "claim-1.md").write_text("# Claim\n")

        pkt = PacketPromotion(
            packet_id="pkt-solo",
            source_id="src-solo",
            run_ids=["run-solo"],
            queue_ids=["q-solo"],
            promoted_paths=["Claims/claim-1.md"],
        )
        commit_packet_promotion(tmp_path, pkt)

        new_count = _count_commits(tmp_path)
        assert new_count == initial_count + 1

        # Verify the commit diff only touches the expected file
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        )
        changed_files = result.stdout.strip().splitlines()
        assert changed_files == ["Claims/claim-1.md"]


# ---------------------------------------------------------------------------
# AC-REV-004-3: Commit subject matches schema
# ---------------------------------------------------------------------------

class TestCommitSubjectSchema:

    def test_commit_subject_matches(self, tmp_path: Path):
        _init_git_repo(tmp_path)

        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "x.md").write_text("content")

        pkt = PacketPromotion(
            packet_id="pkt-fmt",
            source_id="src-fmt",
            run_ids=["run-b", "run-a"],
            queue_ids=["q-1"],
            promoted_paths=["Sources/x.md"],
        )
        commit_packet_promotion(tmp_path, pkt)

        subjects = _get_log(tmp_path, 1)
        assert subjects[0] == "graduate packet=pkt-fmt source=src-fmt run_ids=run-a,run-b"


# ---------------------------------------------------------------------------
# AC-REV-004-4: Commit body has queue_ids in lexical order
# ---------------------------------------------------------------------------

class TestCommitBodyOrder:

    def test_body_has_sorted_queue_ids(self, tmp_path: Path):
        _init_git_repo(tmp_path)

        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "y.md").write_text("content")

        pkt = PacketPromotion(
            packet_id="pkt-body",
            source_id="src-body",
            run_ids=["run-1"],
            queue_ids=["q-z", "q-a", "q-m"],
            promoted_paths=["Sources/y.md"],
        )
        commit_packet_promotion(tmp_path, pkt)

        body = _get_commit_body(tmp_path)
        lines = body.splitlines()
        # queue_ids should appear in sorted order
        assert "q-a" in lines[1]
        assert "q-m" in lines[2]
        assert "q-z" in lines[3]


# ---------------------------------------------------------------------------
# AC-REV-004-5: Failed commit → no partial mutations (atomicity)
# ---------------------------------------------------------------------------

class TestAtomicity:

    def test_git_add_failure_raises(self, tmp_path: Path):
        _init_git_repo(tmp_path)

        # Try to commit a non-existent file
        pkt = PacketPromotion(
            packet_id="pkt-fail",
            source_id="src-fail",
            run_ids=["run-1"],
            queue_ids=["q-1"],
            promoted_paths=["Sources/nonexistent.md"],
        )
        with pytest.raises(GitModeError):
            commit_packet_promotion(tmp_path, pkt)

    def test_not_a_git_repo_raises(self, tmp_path: Path):
        # tmp_path without git init
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "note.md").write_text("content")

        pkt = PacketPromotion(
            packet_id="pkt-no-git",
            source_id="src-no-git",
            run_ids=["run-1"],
            queue_ids=["q-1"],
            promoted_paths=["Sources/note.md"],
        )
        with pytest.raises(GitModeError):
            commit_packet_promotion(tmp_path, pkt)


# ---------------------------------------------------------------------------
# apply_git_mode_promotions
# ---------------------------------------------------------------------------

class TestApplyGitModePromotions:

    def test_applies_multiple_packets(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "Sources").mkdir()

        packets = []
        for i in range(3):
            fname = f"note-{i}.md"
            (tmp_path / "Sources" / fname).write_text(f"# Note {i}\n")
            packets.append(PacketPromotion(
                packet_id=f"pkt-{i}",
                source_id=f"src-{i}",
                run_ids=[f"run-{i}"],
                queue_ids=[f"q-{i}"],
                promoted_paths=[f"Sources/{fname}"],
            ))

        results = apply_git_mode_promotions(tmp_path, packets)
        assert len(results) == 3
        for r in results:
            assert "commit_hash" in r
            assert len(r["commit_hash"]) == 40  # git SHA

    def test_returns_sorted_queue_ids(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "Sources").mkdir()
        (tmp_path / "Sources" / "f.md").write_text("x")

        packets = [PacketPromotion(
            packet_id="pkt-1",
            source_id="src-1",
            run_ids=["r-1"],
            queue_ids=["q-c", "q-a", "q-b"],
            promoted_paths=["Sources/f.md"],
        )]

        results = apply_git_mode_promotions(tmp_path, packets)
        assert results[0]["queue_ids"] == ["q-a", "q-b", "q-c"]
