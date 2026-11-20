"""Harness concurrency lock & git-worktree coordinator for LedgerLens.

Stores active harness claims in `<git-common-dir>/harness-locks.json` so all
git worktrees (Antigravity, ZCode, Claude Code, Codex, etc.) share one atomic
lock registry without dirtying any branch's working tree.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def _git_common_dir(repo: Path) -> Path:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    raw = Path(res.stdout.strip())
    return raw if raw.is_absolute() else (repo / raw).resolve()


def _lock_file(repo: Path) -> Path:
    return _git_common_dir(repo) / "harness-locks.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {"claims": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _norm_path(p: str) -> str:
    return p.replace("\\", "/").strip().rstrip("/")


def _paths_overlap(a: str, b: str) -> bool:
    na, nb = _norm_path(a), _norm_path(b)
    if na == nb:
        return True
    return na.startswith(nb + "/") or nb.startswith(na + "/")


def cmd_claim(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    lf = _lock_file(repo)
    data = _load(lf)
    claims = [c for c in data.get("claims", []) if c["harness"] != args.harness]

    requested_paths = [_norm_path(p) for p in args.paths]
    requested_wt = _norm_path(str(Path(args.worktree).resolve()))

    for other in claims:
        if _norm_path(other["worktree"]) == requested_wt:
            print(
                f"CONFLICT: worktree '{requested_wt}' is already claimed by '{other['harness']}' "
                f"(branch: {other['branch']}). Use a separate git worktree.",
                file=sys.stderr,
            )
            return 2
        if other["branch"] == args.branch:
            print(
                f"CONFLICT: branch '{args.branch}' is already claimed by '{other['harness']}'.",
                file=sys.stderr,
            )
            return 2
        for rp in requested_paths:
            for op in other["paths"]:
                if _paths_overlap(rp, op):
                    print(
                        f"CONFLICT: path '{rp}' overlaps with '{op}' claimed by "
                        f"'{other['harness']}' (worktree: {other['worktree']}).",
                        file=sys.stderr,
                    )
                    return 2

    claims.append(
        {
            "harness": args.harness,
            "branch": args.branch,
            "worktree": requested_wt,
            "paths": requested_paths,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    data["claims"] = claims
    _save(lf, data)
    print(f"OK: '{args.harness}' claimed branch '{args.branch}' in '{requested_wt}' for {requested_paths}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    lf = _lock_file(repo)
    data = _load(lf)
    before = len(data.get("claims", []))
    data["claims"] = [c for c in data.get("claims", []) if c["harness"] != args.harness]
    _save(lf, data)
    removed = before - len(data["claims"])
    print(f"OK: released {removed} claim(s) for '{args.harness}'.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    lf = _lock_file(repo)
    data = _load(lf)
    claims = data.get("claims", [])
    if not claims:
        print("No active harness claims.")
        return 0
    for c in claims:
        print(
            f"- {c['harness']} | branch={c['branch']} | worktree={c['worktree']} "
            f"| paths={', '.join(c['paths'])}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LedgerLens multi-harness lock & worktree coordinator")
    parser.add_argument("--repo", default=".", help="Path inside the LedgerLens git repository")
    sub = parser.add_subparsers(dest="command", required=True)

    p_claim = sub.add_parser("claim", help="Claim a worktree, branch, and owned file paths")
    p_claim.add_argument("--harness", required=True, help="Harness id, e.g. antigravity or zcode")
    p_claim.add_argument("--branch", required=True, help="Feature branch name (never main)")
    p_claim.add_argument("--worktree", required=True, help="Dedicated git worktree path")
    p_claim.add_argument("--paths", nargs="+", required=True, help="Owned relative file/dir paths")
    p_claim.set_defaults(func=cmd_claim)

    p_rel = sub.add_parser("release", help="Release active claim for a harness")
    p_rel.add_argument("--harness", required=True)
    p_rel.set_defaults(func=cmd_release)

    p_stat = sub.add_parser("status", help="List active harness claims")
    p_stat.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if args.command == "claim" and args.branch == "main":
        print("ERROR: Cannot claim 'main'. Always use a feat/, fix/, docs/, or chore/ branch.", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
