"""Line-level merge preview, the host-side stand-in for git merge-tree."""

from dataclasses import dataclass


@dataclass
class Conflict:
    path: str
    left: str
    right: str


def merge_preview(
    base: dict[str, str],
    left: dict[str, str],
    right: dict[str, str],
) -> tuple[dict[str, str], list[Conflict]]:
    """Three-way merge of path to text. Conflicts keep both sides and are listed."""
    paths = set(base) | set(left) | set(right)
    merged: dict[str, str] = {}
    conflicts: list[Conflict] = []
    for path in sorted(paths):
        base_text = base.get(path, "")
        left_text = left.get(path, base_text)
        right_text = right.get(path, base_text)
        if left_text == right_text:
            merged[path] = left_text
            continue
        if left_text == base_text:
            merged[path] = right_text
            continue
        if right_text == base_text:
            merged[path] = left_text
            continue
        conflicts.append(Conflict(path=path, left=left_text, right=right_text))
        merged[path] = f"{left_text}\n<<<<<<<\n{right_text}"
    return merged, conflicts
