#!/usr/bin/env python3
"""
Normalize Markdown formatting in docs/.

Rules:
1) Headers start with '#' and are not in code fences. Remove leading whitespace if present.
2) If a line ends with ':' and the next non-empty line is a list item, ensure a blank line
   separates them (space between ':' and first bullet point).
3) List item indentation must be a multiple of 4 spaces (0,4,8,...). Normalize to the next
   multiple of 4 for indented lists.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

FENCE_RE = re.compile(r"^\s*([`~]{3,})(.*)$")
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+\S")
LIST_RE = re.compile(r"^(\s*)(?:[-+*]|\d+\.)\s+")


def iter_md_files(root: Path) -> Iterable[Path]:
    return root.rglob("*.md")


def normalize_indent(indent_len: int) -> int:
    if indent_len <= 0:
        return 0
    # Round up to the next multiple of 4 to preserve nesting depth.
    return ((indent_len + 3) // 4) * 4


def _format_line_list(lines: List[int], max_items: int = 20) -> str:
    if not lines:
        return ""
    if len(lines) <= max_items:
        return ", ".join(str(n) for n in lines)
    head = ", ".join(str(n) for n in lines[:max_items])
    return f"{head}, ... (+{len(lines) - max_items} more)"


def _parse_fence(line: str) -> Optional[Tuple[str, int]]:
    match = FENCE_RE.match(line)
    if not match:
        return None
    fence = match.group(1)
    if fence[0] not in ("`", "~"):
        return None
    return fence[0], len(fence)


def _is_fence_close(line: str, fence_char: str, fence_len: int) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith(fence_char * fence_len):
        return False
    # Closing fence can be longer than opening, but must be same char
    run = 0
    for ch in stripped:
        if ch == fence_char:
            run += 1
        else:
            break
    return run >= fence_len


def process_file(
    path: Path,
) -> Optional[Tuple[int, int, int, List[int], List[int], List[int]]]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    new_lines: list[str] = []
    in_fence = False
    fence_char: Optional[str] = None
    fence_len: Optional[int] = None
    changed = False
    header_fixes = 0
    blank_lines = 0
    heading_blank_lines = 0
    list_indent_fixes = 0
    header_lines: List[int] = []
    blank_lines_at: List[int] = []
    heading_blank_lines_at: List[int] = []
    list_indent_lines: List[int] = []

    last_list_indent_len: Optional[int] = None
    last_list_fixed_len: Optional[int] = None

    i = 0
    while i < len(lines):
        line = lines[i]

        if in_fence:
            if fence_char is not None and fence_len is not None:
                if _is_fence_close(line, fence_char, fence_len):
                    in_fence = False
                    fence_char = None
                    fence_len = None
            new_lines.append(line)
            i += 1
            continue

        fence = _parse_fence(line)
        if fence:
            in_fence = True
            fence_char, fence_len = fence
            new_lines.append(line)
            i += 1
            continue

        # Rule 1: headers should start at column 0
        if HEADING_RE.match(line):
            stripped = line.lstrip()
            if stripped != line:
                line = stripped
                changed = True
                header_fixes += 1
                header_lines.append(i + 1)

            if i + 1 < len(lines) and lines[i + 1] != "":
                new_lines.append(line)
                new_lines.append("")
                changed = True
                heading_blank_lines += 1
                heading_blank_lines_at.append(i + 1)
                i += 1
                continue

        # Rule 2: line ending with ':' before a list or code fence needs a blank line
        if line.rstrip().endswith(":"):
            j = i + 1
            # look ahead to next non-empty line
            while j < len(lines) and lines[j] == "":
                j += 1
            if j < len(lines):
                m = LIST_RE.match(lines[j])
                is_fence_next = _parse_fence(lines[j]) is not None
                is_current_list = LIST_RE.match(line) is not None
                if (
                    (m or is_fence_next)
                    and not is_current_list
                    and i + 1 < len(lines)
                    and lines[i + 1] != ""
                ):
                    new_lines.append(line)
                    new_lines.append("")
                    changed = True
                    blank_lines += 1
                    blank_lines_at.append(i + 1)
                    i += 1
                    continue

        # Rule 3: normalize list indentation
        m = LIST_RE.match(line)
        if m:
            indent = m.group(1)
            indent_len = len(indent.replace("\t", "    "))
            fixed_len = normalize_indent(indent_len)
            if (
                last_list_indent_len is not None
                and last_list_fixed_len is not None
                and indent_len > last_list_indent_len
                and fixed_len <= last_list_fixed_len
            ):
                fixed_len = last_list_fixed_len + 4

            if fixed_len != indent_len:
                line = " " * fixed_len + line[len(indent) :]
                changed = True
                list_indent_fixes += 1
                list_indent_lines.append(i + 1)

            last_list_indent_len = indent_len
            last_list_fixed_len = fixed_len

        new_lines.append(line)
        i += 1

    new_content = "\n".join(new_lines)
    if original.endswith("\n"):
        new_content += "\n"

    if changed:
        path.write_text(new_content, encoding="utf-8")
        return (
            header_fixes,
            blank_lines,
            list_indent_fixes,
            header_lines,
            blank_lines_at,
            list_indent_lines,
            heading_blank_lines,
            heading_blank_lines_at,
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize markdown formatting in docs."
    )
    parser.add_argument(
        "--docs",
        default="/mnt/ssd2/repos/arcadedb-embedded-python/bindings/python/docs",
        help="Path to docs directory",
    )
    args = parser.parse_args()

    docs_root = Path(args.docs)
    if not docs_root.exists():
        raise SystemExit(f"Docs path does not exist: {docs_root}")

    changed_files = []
    total_header = 0
    total_blank = 0
    total_indent = 0
    for md_file in iter_md_files(docs_root):
        result = process_file(md_file)
        if result:
            (
                header_fixes,
                blank_lines,
                list_indent_fixes,
                header_lines,
                blank_lines_at,
                list_indent_lines,
                heading_blank_lines,
                heading_blank_lines_at,
            ) = result
            changed_files.append(
                (
                    md_file,
                    header_fixes,
                    blank_lines,
                    list_indent_fixes,
                    header_lines,
                    blank_lines_at,
                    list_indent_lines,
                    heading_blank_lines,
                    heading_blank_lines_at,
                )
            )
            total_header += header_fixes
            total_blank += blank_lines
            total_indent += list_indent_fixes
            total_blank += heading_blank_lines

    print(f"Updated {len(changed_files)} files")
    print(
        "Totals: "
        f"headers fixed={total_header}, "
        f"blank lines inserted={total_blank}, "
        f"list indents normalized={total_indent}"
    )

    for (
        path,
        header_fixes,
        blank_lines,
        list_indent_fixes,
        header_lines,
        blank_lines_at,
        list_indent_lines,
        heading_blank_lines,
        heading_blank_lines_at,
    ) in changed_files:
        print(f"\n{path}")
        if header_fixes:
            print(f"  Header fixes: {header_fixes}")
            print(f"    Lines: {_format_line_list(header_lines)}")
        if blank_lines:
            print(f"  Blank lines inserted: {blank_lines}")
            print(f"    Lines: {_format_line_list(blank_lines_at)}")
        if heading_blank_lines:
            print(f"  Heading blank lines inserted: {heading_blank_lines}")
            print(f"    Lines: {_format_line_list(heading_blank_lines_at)}")
        if list_indent_fixes:
            print(f"  List indents normalized: {list_indent_fixes}")
            print(f"    Lines: {_format_line_list(list_indent_lines)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
