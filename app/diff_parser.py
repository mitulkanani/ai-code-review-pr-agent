from dataclasses import dataclass
import re


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class AddedLine:
    number: int
    text: str


def parse_added_lines(patch: str | None) -> list[AddedLine]:
    """Return only added lines and their new-file line numbers from a unified diff.

    Context lines advance the new-file counter; deleted lines do not. This keeps
    findings anchored to lines GitHub can display in a PR diff.
    """
    if not patch:
        return []

    added: list[AddedLine] = []
    new_line: int | None = None
    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            match = _HUNK_RE.match(raw_line)
            new_line = int(match.group(3)) if match else None
            continue
        if new_line is None:
            continue
        if raw_line.startswith("+++") or raw_line.startswith("---"):
            continue
        if raw_line.startswith("+"):
            added.append(AddedLine(number=new_line, text=raw_line[1:]))
            new_line += 1
        elif raw_line.startswith("-"):
            continue
        elif raw_line.startswith(" "):
            new_line += 1
        elif raw_line.startswith("\\"):
            continue
    return added


def count_patch_changes(patch: str | None) -> tuple[int, int, int]:
    """Return additions, deletions, and added lines with usable line mappings."""
    if not patch:
        return 0, 0, 0
    additions = deletions = 0
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions, len(parse_added_lines(patch))
