#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

KEEP_ROOT_FILENAMES = {
    "run_status.json",
    "search_run_status.json",
    "dependency_versions.json",
    "disk_usage_du.json",
    "disk_usage_du.txt",
}


@dataclass
class RunCleanupPlan:
    run_dir: Path
    backend: str | None
    result_files: list[Path]
    delete_paths: list[Path]
    delete_bytes: int
    skip_reason: str | None = None


def iter_result_files(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.glob("results*.json") if path.is_file())


def detect_backend(run_dir: Path, result_files: Iterable[Path]) -> str | None:
    for result_file in result_files:
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        config = payload.get("config")
        if isinstance(config, dict):
            backend = config.get("backend")
            if backend:
                return str(backend)

        env = payload.get("environment")
        if isinstance(env, dict):
            backend = env.get("backend")
            if backend:
                return str(backend)

    name = run_dir.name.lower()
    if "arcadedb" in name:
        return "arcadedb"
    return None


def should_keep_root_file(path: Path, result_files: set[Path]) -> bool:
    if path in result_files:
        return True
    if path.name in KEEP_ROOT_FILENAMES:
        return True
    return False


def path_size_bytes(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def build_cleanup_plan(run_dir: Path) -> RunCleanupPlan | None:
    if not run_dir.is_dir():
        return None

    result_files = iter_result_files(run_dir)
    if not result_files:
        return None

    backend = detect_backend(run_dir, result_files)
    if backend and backend.startswith("arcadedb"):
        return RunCleanupPlan(
            run_dir=run_dir,
            backend=backend,
            result_files=result_files,
            delete_paths=[],
            delete_bytes=0,
            skip_reason="arcadedb backend preserved",
        )

    result_file_set = set(result_files)
    delete_paths: list[Path] = []
    delete_bytes = 0

    for child in sorted(run_dir.iterdir()):
        if should_keep_root_file(child, result_file_set):
            continue
        delete_paths.append(child)
        delete_bytes += path_size_bytes(child)

    return RunCleanupPlan(
        run_dir=run_dir,
        backend=backend,
        result_files=result_files,
        delete_paths=delete_paths,
        delete_bytes=delete_bytes,
    )


def apply_plan(plan: RunCleanupPlan) -> None:
    for path in plan.delete_paths:
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove non-ArcadeDB benchmark payloads from run directories that already "
            "contain saved results*.json files."
        )
    )
    parser.add_argument(
        "--root",
        default="my_test_databases",
        help="Benchmark output root directory (default: my_test_databases)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletions. Without this flag, only print a dry-run summary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each run directory and paths selected for deletion.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root directory does not exist: {root}")

    plans = [
        plan
        for run_dir in sorted(root.iterdir())
        if (plan := build_cleanup_plan(run_dir)) is not None
    ]

    eligible = [plan for plan in plans if plan.skip_reason is None]
    skipped = [plan for plan in plans if plan.skip_reason is not None]
    deletable = [plan for plan in eligible if plan.delete_paths]
    total_bytes = sum(plan.delete_bytes for plan in deletable)

    print(f"Scanned run directories: {len(plans)}")
    print(f"ArcadeDB-preserved run directories: {len(skipped)}")
    print(f"Non-ArcadeDB runs with removable payloads: {len(deletable)}")
    print(f"Estimated reclaimable space: {format_bytes(total_bytes)}")

    if args.verbose:
        for plan in plans:
            backend = plan.backend or "unknown"
            print(f"\n[{backend}] {plan.run_dir.name}")
            if plan.skip_reason:
                print(f"  skip: {plan.skip_reason}")
                continue
            if not plan.delete_paths:
                print("  delete: nothing")
                continue
            print(f"  delete_bytes: {format_bytes(plan.delete_bytes)}")
            for path in plan.delete_paths:
                rel = path.relative_to(plan.run_dir)
                print(f"  delete: {rel}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to delete payloads.")
        return

    for plan in deletable:
        apply_plan(plan)

    print(f"\nDeleted payloads from {len(deletable)} run directories.")
    print(f"Reclaimed approximately: {format_bytes(total_bytes)}")


if __name__ == "__main__":
    main()
