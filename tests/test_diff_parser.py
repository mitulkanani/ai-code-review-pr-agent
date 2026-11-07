from app.diff_parser import count_patch_changes, parse_added_lines


def test_added_lines_keep_new_file_line_numbers_across_changes() -> None:
    patch = """@@ -1,3 +1,4 @@
 context one
-old line
+new line
+second new line
 context three
"""
    assert [(item.number, item.text) for item in parse_added_lines(patch)] == [
        (2, "new line"),
        (3, "second new line"),
    ]


def test_multiple_hunks_and_removed_lines() -> None:
    patch = """@@ -10,2 +10,2 @@
 old
+new
@@ -40,1 +40,2 @@
 context
+another
"""
    assert [(item.number, item.text) for item in parse_added_lines(patch)] == [(11, "new"), (41, "another")]


def test_binary_or_missing_patch_has_no_lines() -> None:
    assert parse_added_lines(None) == []
    assert count_patch_changes(None) == (0, 0, 0)
