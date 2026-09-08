"""Validated commit-to-commit file-set comparison.

Normalizes GitHub commit data, compares file sets with set algebra, and
validates that total_A = only_A + shared and total_B = only_B + shared
before any answer is generated.
"""

from __future__ import annotations

import re
from typing import Any


class CommitCompareError(ValueError):
    """Raised when comparison counts cannot be reconciled with GitHub data."""


def normalize_path(path: str) -> str:
    """Normalize a repository path for set comparison."""
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = re.sub(r"/+", "/", cleaned)
    return cleaned.lstrip("/")


def normalize_commit(detail: dict) -> dict:
    """Build a normalized commit view from GitHub commit detail."""
    files_by_path: dict[str, dict[str, Any]] = {}
    for entry in detail.get("files") or []:
        path = normalize_path(entry.get("filename") or "")
        if not path:
            continue
        files_by_path[path] = {
            "filename": path,
            "status": entry.get("status", "modified"),
            "additions": entry.get("additions", 0),
            "deletions": entry.get("deletions", 0),
            "changes": entry.get("changes", 0),
            "patch": entry.get("patch"),
        }

    # Include authoritative filenames when GitHub returned more than we stored
    for path in detail.get("all_filenames") or []:
        norm = normalize_path(path)
        if norm and norm not in files_by_path:
            files_by_path[norm] = {
                "filename": norm,
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "changes": 0,
                "patch": None,
            }

    paths = sorted(files_by_path.keys())
    authoritative_count = detail.get("file_count")
    if authoritative_count is None:
        authoritative_count = len(paths)

    return {
        "sha": detail.get("sha") or "",
        "short_sha": detail.get("short_sha") or (detail.get("sha") or "")[:7],
        "title": detail.get("title") or "",
        "author": detail.get("author") or "unknown",
        "date": detail.get("date") or "",
        "files_by_path": files_by_path,
        "paths": paths,
        "file_count": authoritative_count,
        "diff_available": bool(detail.get("has_diff")),
        "diff_excerpt": detail.get("diff_excerpt") or "",
        "parent_shas": list(detail.get("parent_shas") or []),
    }


def _extract_patch_for_file(detail: dict, path: str) -> str | None:
    norm = normalize_path(path)
    for entry in detail.get("files") or []:
        if normalize_path(entry.get("filename") or "") == norm:
            return entry.get("patch")
    excerpt = detail.get("diff_excerpt") or ""
    marker = f"--- {path} ---"
    alt_marker = f"--- {norm} ---"
    for label in (marker, alt_marker):
        if label in excerpt:
            start = excerpt.index(label)
            rest = excerpt[start + len(label) :].lstrip("\n")
            next_file = rest.find("\n--- ")
            return rest[:next_file] if next_file != -1 else rest
    return None


def compare_commits(detail_a: dict, detail_b: dict) -> dict:
    """Compare two commits with validated set algebra."""
    norm_a = normalize_commit(detail_a)
    norm_b = normalize_commit(detail_b)

    set_a = set(norm_a["paths"])
    set_b = set(norm_b["paths"])
    overlap = set_a & set_b
    only_a = set_a - set_b
    only_b = set_b - set_a

    total_a = norm_a["file_count"]
    total_b = norm_b["file_count"]
    overlap_count = len(overlap)
    only_a_count = len(only_a)
    only_b_count = len(only_b)

    validation_errors: list[str] = []

    if total_a != only_a_count + overlap_count:
        validation_errors.append(
            f"Commit A: total ({total_a}) != only_A ({only_a_count}) + shared ({overlap_count})"
        )
    if total_b != only_b_count + overlap_count:
        validation_errors.append(
            f"Commit B: total ({total_b}) != only_B ({only_b_count}) + shared ({overlap_count})"
        )
    if overlap & only_a or overlap & only_b:
        validation_errors.append("A file appears in both shared and unique sets")
    if only_a & only_b:
        validation_errors.append("A file appears in both only_A and only_B")

    listed_a = len(set_a)
    listed_b = len(set_b)
    if listed_a < total_a:
        validation_errors.append(
            f"Commit A file list incomplete: GitHub reports {total_a} files but only {listed_a} paths loaded"
        )
    if listed_b < total_b:
        validation_errors.append(
            f"Commit B file list incomplete: GitHub reports {total_b} files but only {listed_b} paths loaded"
        )

    shared_analysis: list[dict[str, Any]] = []
    for path in sorted(overlap):
        patch_a = _extract_patch_for_file(detail_a, path)
        patch_b = _extract_patch_for_file(detail_b, path)
        shared_analysis.append(
            {
                "path": path,
                "commit_a_has_diff": bool(patch_a),
                "commit_b_has_diff": bool(patch_b),
                "commit_a_patch": (patch_a or "")[:2000] or None,
                "commit_b_patch": (patch_b or "")[:2000] or None,
            }
        )

    result = {
        "commit_a": norm_a,
        "commit_b": norm_b,
        "overlap": sorted(overlap),
        "only_a": sorted(only_a),
        "only_b": sorted(only_b),
        "counts": {
            "total_a": total_a,
            "total_b": total_b,
            "overlap": overlap_count,
            "only_a": only_a_count,
            "only_b": only_b_count,
        },
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "shared_analysis": shared_analysis,
    }
    return result


def format_commit_compare_block(detail_a: dict, detail_b: dict) -> str:
    """Format a validated comparison for the LLM or direct reply."""
    comparison = compare_commits(detail_a, detail_b)
    if not comparison["valid"]:
        errors = "\n".join(f"• {e}" for e in comparison["validation_errors"])
        return (
            "COMMIT COMPARISON DATA INCONSISTENCY\n\n"
            "The file-set comparison could not be validated against GitHub data:\n"
            f"{errors}\n\n"
            "Do not present file counts until the data is reconciled."
        )

    norm_a = comparison["commit_a"]
    norm_b = comparison["commit_b"]
    counts = comparison["counts"]
    lines = [
        "COMMIT COMPARISON (validated file-set math)",
        "",
        f"Commit A: {norm_a['short_sha']} — \"{norm_a['title']}\" ({norm_a['date']})",
        f"Commit B: {norm_b['short_sha']} — \"{norm_b['title']}\" ({norm_b['date']})",
        "",
        "FILE SUMMARY (use these exact counts — do not recalculate)",
        f"Commit A total changed files: {counts['total_a']}",
        f"Commit B total changed files: {counts['total_b']}",
        f"Changed in both commits (shared): {counts['overlap']}",
        f"Only in Commit A (unique to A, NOT including shared): {counts['only_a']}",
        f"Only in Commit B (unique to B, NOT including shared): {counts['only_b']}",
        "",
        f"Validation: total_A ({counts['total_a']}) = only_A ({counts['only_a']}) + shared ({counts['overlap']})",
        f"Validation: total_B ({counts['total_b']}) = only_B ({counts['only_b']}) + shared ({counts['overlap']})",
        "",
    ]

    if comparison["overlap"]:
        lines.append(f"FILES CHANGED IN BOTH ({counts['overlap']} file{'s' if counts['overlap'] != 1 else ''}):")
        for path in comparison["overlap"]:
            lines.append(f"• {path}")
        lines.append("")
        for item in comparison["shared_analysis"]:
            lines.append(f"Shared file: {item['path']}")
            if item["commit_a_patch"]:
                lines.append(f"Commit A diff excerpt:\n{item['commit_a_patch']}")
            elif norm_a["diff_available"]:
                lines.append(
                    "Commit A: file appears in changed-file list but no line-level diff excerpt is available."
                )
            else:
                lines.append("Commit A: diff not available for this file.")
            if item["commit_b_patch"]:
                lines.append(f"Commit B diff excerpt:\n{item['commit_b_patch']}")
            elif norm_b["diff_available"]:
                lines.append(
                    "Commit B: file appears in changed-file list but no line-level diff excerpt is available."
                )
            else:
                lines.append("Commit B: diff not available for this file.")
            lines.append("")
    else:
        lines.append("FILES CHANGED IN BOTH: 0 files")
        lines.append("")

    lines.append(
        f"FILES ONLY IN COMMIT A ({counts['only_a']} file{'s' if counts['only_a'] != 1 else ''} — excludes shared files):"
    )
    if comparison["only_a"]:
        for path in comparison["only_a"]:
            meta = norm_a["files_by_path"].get(path, {})
            lines.append(
                f"• {path} ({meta.get('status', 'modified')}, "
                f"+{meta.get('additions', 0)}/-{meta.get('deletions', 0)})"
            )
    else:
        lines.append("(none)")
    lines.append("")

    lines.append(
        f"FILES ONLY IN COMMIT B ({counts['only_b']} file{'s' if counts['only_b'] != 1 else ''} — excludes shared files):"
    )
    if comparison["only_b"]:
        for path in comparison["only_b"]:
            meta = norm_b["files_by_path"].get(path, {})
            lines.append(
                f"• {path} ({meta.get('status', 'modified')}, "
                f"+{meta.get('additions', 0)}/-{meta.get('deletions', 0)})"
            )
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("ANALYSIS RULES FOR THIS COMPARISON:")
    lines.append(
        "• VERIFIED: file membership comes from GitHub changed-file lists above."
    )
    lines.append(
        "• VERIFIED: line-level changes require a diff excerpt for that commit and file."
    )
    lines.append(
        "• Do NOT say a file is 'only in A' if it appears under FILES CHANGED IN BOTH."
    )
    lines.append(
        "• Do NOT attach a total changed count to a unique-only list (e.g. never 'only in A (19 total)')."
    )
    lines.append(
        "• INFERENCE: label purpose/impact guesses as inference; say UNKNOWN when diff is missing."
    )

    return "\n".join(lines)


def answer_commit_compare_without_llm(detail_a: dict, detail_b: dict) -> str:
    comparison = compare_commits(detail_a, detail_b)
    if not comparison["valid"]:
        return format_commit_compare_block(detail_a, detail_b)

    counts = comparison["counts"]
    norm_a = comparison["commit_a"]
    norm_b = comparison["commit_b"]
    lines = [
        "Commit comparison",
        "",
        f"Commit A: {norm_a['short_sha']} — \"{norm_a['title']}\"",
        f"Commit B: {norm_b['short_sha']} — \"{norm_b['title']}\"",
        "",
        "File summary",
        f"• Commit A total changed: {counts['total_a']}",
        f"• Commit B total changed: {counts['total_b']}",
        f"• Changed in both: {counts['overlap']}",
        f"• Only in Commit A: {counts['only_a']}",
        f"• Only in Commit B: {counts['only_b']}",
        "",
    ]

    if comparison["overlap"]:
        lines.append(f"Shared ({counts['overlap']}):")
        for path in comparison["overlap"]:
            lines.append(f"• {path}")
        lines.append("")

    if comparison["only_a"]:
        lines.append(f"Only in Commit A ({counts['only_a']}):")
        for path in comparison["only_a"][:25]:
            lines.append(f"• {path}")
        if counts["only_a"] > 25:
            lines.append(f"• … and {counts['only_a'] - 25} more")
        lines.append("")

    if comparison["only_b"]:
        lines.append(f"Only in Commit B ({counts['only_b']}):")
        for path in comparison["only_b"]:
            lines.append(f"• {path}")
        lines.append("")
    elif counts["only_b"] == 0:
        lines.append("Only in Commit B: 0 files")
        lines.append("")

    return "\n".join(lines)


def _chrono_position_label(index: int, total: int) -> str:
    if total == 1:
        return "only commit"
    if index == 0:
        return "oldest"
    if index == total - 1:
        return "newest"
    if total == 3 and index == 1:
        return "middle"
    return f"position {index + 1} of {total}"


def order_commits_for_analysis(details: list[dict]) -> dict:
    """Split repository order (newest-first) from chronological order (oldest-first)."""
    repository_order = list(details)
    chrono_sorted = sorted(
        details,
        key=lambda d: (d.get("date") or "", d.get("sha") or ""),
    )
    dates = [d.get("date") or "" for d in chrono_sorted]
    ordering_valid = all(
        dates[i] <= dates[i + 1] for i in range(len(dates) - 1)
    ) if len(dates) > 1 else True

    warnings: list[str] = []
    if not ordering_valid:
        warnings.append(
            "Commit timestamps do not provide a strictly consistent ordering; "
            "verify against repository history before drawing timeline conclusions."
        )

    sha_set = {d.get("sha") for d in chrono_sorted if d.get("sha")}
    for i in range(1, len(chrono_sorted)):
        parents = set(chrono_sorted[i].get("parent_shas") or [])
        if parents and not parents.intersection(sha_set):
            warnings.append(
                f"Parent relationship for {chrono_sorted[i].get('short_sha', '')[:7]} "
                "is not among the selected commits."
            )

    return {
        "repository_order": repository_order,
        "chronological_order": chrono_sorted,
        "ordering_valid": ordering_valid and not warnings,
        "ordering_warnings": warnings,
    }


def _membership_buckets(
    path_sets: list[set[str]], shas: list[str]
) -> dict[str, list[str]]:
    """Exact file membership across N commits (e.g. only A, A+B, all three)."""
    if not path_sets:
        return {}
    all_paths: set[str] = set()
    for paths in path_sets:
        all_paths.update(paths)
    buckets: dict[str, list[str]] = {}
    n = len(path_sets)
    for path in sorted(all_paths):
        present = {i for i in range(n) if path in path_sets[i]}
        if len(present) == 1:
            idx = next(iter(present))
            label = f"only {shas[idx][:7]}"
        elif len(present) == n:
            label = "all commits"
        else:
            label = " + ".join(sorted(shas[i][:7] for i in present))
        buckets.setdefault(label, []).append(path)
    return buckets


def compare_multiple_commits(details: list[dict]) -> dict:
    """Compare N commits with chronological ordering for engineering evolution."""
    ordering = order_commits_for_analysis(details)
    chrono_details = ordering["chronological_order"]
    normalized = [normalize_commit(d) for d in chrono_details]
    path_sets = [set(norm["paths"]) for norm in normalized]
    shas = [norm["short_sha"] for norm in normalized]

    file_to_commits: dict[str, list[int]] = {}
    for idx, paths in enumerate(path_sets):
        for path in paths:
            file_to_commits.setdefault(path, []).append(idx)

    repeatedly_touched = {
        path: sorted(indices)
        for path, indices in file_to_commits.items()
        if len(indices) > 1
    }

    unique_per_commit: list[list[str]] = []
    for idx, paths in enumerate(path_sets):
        others: set[str] = set()
        for j, other in enumerate(path_sets):
            if j != idx:
                others.update(other)
        unique_per_commit.append(sorted(paths - others))

    file_evolution: dict[str, list[dict[str, Any]]] = {}
    for path, indices in repeatedly_touched.items():
        steps = []
        for idx in indices:
            norm = normalized[idx]
            entry = norm["files_by_path"].get(path, {})
            steps.append(
                {
                    "sha": norm["short_sha"],
                    "position": _chrono_position_label(idx, len(normalized)),
                    "date": norm["date"],
                    "has_diff": bool(entry.get("patch") or norm["diff_available"]),
                }
            )
        file_evolution[path] = steps

    membership = _membership_buckets(path_sets, shas)

    return {
        "repository_order": [normalize_commit(d) for d in ordering["repository_order"]],
        "commits": normalized,
        "chronological_order": normalized,
        "ordering_valid": ordering["ordering_valid"],
        "ordering_warnings": ordering["ordering_warnings"],
        "file_to_commits": file_to_commits,
        "repeatedly_touched": repeatedly_touched,
        "unique_per_commit": unique_per_commit,
        "membership_buckets": membership,
        "file_evolution": file_evolution,
        "valid": True,
    }


def format_multi_commit_compare_block(
    details: list[dict], comparison: dict | None = None
) -> str:
    """Format multi-commit analysis — chronological order for evolution, SHAs not ambiguous numbers."""
    comparison = comparison or compare_multiple_commits(details)
    chrono = comparison["commits"]
    repo = comparison["repository_order"]
    n = len(chrono)
    lines = [
        f"THREE-COMMIT ENGINEERING ANALYSIS" if n == 3 else f"MULTI-COMMIT ENGINEERING ANALYSIS ({n} commits)",
        "",
        "REPOSITORY ORDER (newest → oldest — for recent history display only):",
    ]
    for norm in repo:
        lines.append(
            f"• {norm['short_sha']} (newest→oldest list) — \"{norm['title']}\" "
            f"by {norm['author']} ({norm['date']}) — {norm['file_count']} files"
        )
    lines.append("")
    lines.append("CHRONOLOGICAL ORDER (oldest → newest — use this for engineering evolution):")
    for idx, norm in enumerate(chrono):
        pos = _chrono_position_label(idx, n)
        lines.append(
            f"{idx + 1}. {norm['short_sha']} ({pos}) — \"{norm['title']}\" "
            f"by {norm['author']} ({norm['date']}) — {norm['file_count']} files changed"
        )
    lines.append("")
    lines.append("TIMELINE (oldest → newest):")
    for i, norm in enumerate(chrono):
        lines.append(norm["short_sha"])
        if i < n - 1:
            lines.append("↓")
    lines.append("")

    if comparison.get("ordering_warnings"):
        lines.append("ORDERING WARNINGS:")
        for warning in comparison["ordering_warnings"]:
            lines.append(f"• {warning}")
        lines.append("")

    lines.append("THREE-WAY FILE MEMBERSHIP (exact sets — do not infer):" if n == 3 else f"N-WAY FILE MEMBERSHIP ({n} commits — exact sets, do not infer):")
    for label, paths in sorted(comparison["membership_buckets"].items()):
        lines.append(f"{label} ({len(paths)} file{'s' if len(paths) != 1 else ''}):")
        for path in paths[:15]:
            lines.append(f"  • {path}")
        if len(paths) > 15:
            lines.append(f"  • … and {len(paths) - 15} more")
    lines.append("")

    repeated = comparison["repeatedly_touched"]
    lines.append(
        f"FILES MODIFIED IN MULTIPLE COMMITS ({len(repeated)} file{'s' if len(repeated) != 1 else ''}):"
    )
    if repeated:
        for path in sorted(repeated.keys())[:25]:
            shas_hit = [chrono[i]["short_sha"] for i in repeated[path]]
            lines.append(f"• {path} — {len(shas_hit)} commits: {', '.join(shas_hit)}")
        if len(repeated) > 25:
            lines.append(f"• … and {len(repeated) - 25} more")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("FILE EVOLUTION (oldest → newest; use SHAs, never say an older commit 'revisits' a newer one):")
    for path in sorted(comparison["file_evolution"].keys())[:30]:
        steps = comparison["file_evolution"][path]
        chain = " → ".join(
            f"{s['sha']} ({s['position']})" for s in steps
        )
        diff_note = ", ".join(
            f"{s['sha']}: {'diff available' if s['has_diff'] else 'file list only'}"
            for s in steps
        )
        lines.append(f"• {path}: {chain}")
        lines.append(f"  ({diff_note})")
    if len(comparison["file_evolution"]) > 30:
        lines.append(f"• … and {len(comparison['file_evolution']) - 30} more files")
    lines.append("")

    for idx, (norm, detail) in enumerate(zip(chrono, order_commits_for_analysis(details)["chronological_order"])):
        pos = _chrono_position_label(idx, n).upper()
        lines.append(f"--- {norm['short_sha']} ({pos}) — \"{norm['title']}\" ---")
        unique = comparison["unique_per_commit"][idx]
        lines.append(f"Files unique to this commit among the selected set: {len(unique)}")
        for path in unique[:20]:
            lines.append(f"  • {path}")
        if len(unique) > 20:
            lines.append(f"  • … and {len(unique) - 20} more")
        if detail.get("diff_excerpt"):
            lines.append(f"Diff excerpt:\n{detail['diff_excerpt'][:3500]}")
        else:
            lines.append("Diff excerpt: not available for this commit.")
        lines.append("")

    lines.extend(
        [
            "ANALYSIS RULES:",
            "• Explain engineering evolution in CHRONOLOGICAL ORDER (oldest → newest).",
            "• Refer to commits by SHA and position (oldest/middle/newest), not undefined 'Commit 1/2/3'.",
            "• A later commit may 'revisit' or 'refine' a file; never describe an older commit as revisiting a newer one.",
            "• Oldest: introduced/established/added. Middle: refined/extended/modified. Newest: expanded/integrated/completed.",
            "• Only use evolution verbs when supported by diffs; otherwise say UNKNOWN.",
            "• Repeated file touches establish modification frequency only — instability conclusions are INFERENCE.",
            "• File membership is VERIFIED from GitHub; line-level purpose requires diff evidence.",
            "• Label trajectory interpretation as INFERENCE, not fact.",
        ]
    )
    return "\n".join(lines)


def answer_multi_commit_compare_without_llm(details: list[dict]) -> str:
    comparison = compare_multiple_commits(details)
    chrono = comparison["commits"]
    lines = [
        f"Engineering analysis of the last {len(chrono)} commits",
        "",
        "Chronological order (oldest → newest):",
    ]
    for idx, norm in enumerate(chrono):
        pos = _chrono_position_label(idx, len(chrono))
        lines.append(
            f"{idx + 1}. {norm['short_sha']} ({pos}) — \"{norm['title']}\" "
            f"({norm['file_count']} files, {norm['date']})"
        )
    lines.append("")
    lines.append("Timeline: " + " → ".join(n["short_sha"] for n in chrono))
    lines.append("")
    if comparison["repeatedly_touched"]:
        lines.append("Files modified in more than one commit:")
        for path in sorted(comparison["repeatedly_touched"].keys())[:15]:
            shas_hit = [chrono[i]["short_sha"] for i in comparison["repeatedly_touched"][path]]
            lines.append(f"• {path} ({', '.join(shas_hit)})")
    return "\n".join(lines)
