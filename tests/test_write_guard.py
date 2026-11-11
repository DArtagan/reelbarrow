"""Only the executor changes anything under the video root (*Rules that protect
the library*, in `AGENTS.md`).

Two halves. The static one reads every module in `src/reelbarrow` for the
calls that write, rename or remove, and allows them only where the write is
known to land outside the video root, or is the executor's own. The runtime
one (`share_guard`, used by every test that builds a share) catches what
reading can't see, such as a library writing on a module's behalf. Neither
sees a subprocess's own writes: the media tools the analysis runs are given
files to read.
"""

import ast
import json
from pathlib import Path

import pytest
import share_guard

from reelbarrow import manifest
from reelbarrow.executor import Writer

SOURCE = share_guard.SOURCE

# Modules whose writes are theirs to make, and where they land.
WRITERS = {
    # The share's one choke point, which dry run stops.
    "executor.py": "under the video root",
    # The manifest exporter: a separate process that never mounts the library
    # and writes only in its own --out (docs/exporter.md).
    "exporter.py": "its --out",
    # The ledger, in SQLite under REELBARROW_DATA_DIR.
    "ledger.py": "REELBARROW_DATA_DIR",
}
# Single calls elsewhere, each landing outside the video root.
EXCEPTIONS = {
    # The schema files in docs/, by a developer's `python -m`.
    ("manifest.py", "write_text"),
    ("disc_record.py", "write_text"),
    # A pipeline's stderr, in the system's temporary directory.
    ("analysis/tools.py", "tempfile.TemporaryFile"),
}

# Methods that change a file whatever object they're called on; none is a
# name any other type in the standard library uses for something else.
CHANGING_METHODS = frozenset(
    {
        "write_text",
        "write_bytes",
        "touch",
        "mkdir",
        "makedirs",
        "rmdir",
        "removedirs",
        "unlink",
        "rename",
        "renames",
        "symlink_to",
        "hardlink_to",
        "chmod",
        "lchmod",
        "chown",
        "lchown",
        "utime",
        "rmtree",
        "mkfifo",
        "mknod",
    }
)
# Functions of these modules that change files; for shutil and tempfile, all
# but those listed as reading.
CHANGING_FUNCTIONS = {
    "os": frozenset(
        {
            "open",
            "fdopen",
            "write",
            "remove",
            "replace",
            "link",
            "symlink",
            "truncate",
            "ftruncate",
            "chflags",
            "setxattr",
            "removexattr",
        }
    )
    | CHANGING_METHODS,
    "sqlite3": frozenset({"connect"}),
}
READING = {
    "shutil": frozenset({"which", "disk_usage", "get_terminal_size"}),
    "tempfile": frozenset({"gettempdir"}),
}
WRITING_MODES = frozenset("wax+")


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _changes(module: str, name: str) -> bool:
    if module in READING:
        return name not in READING[module]
    return name in CHANGING_FUNCTIONS.get(module, ())


def _mode_writes(call: ast.Call, position: int) -> bool:
    mode = next((k.value for k in call.keywords if k.arg == "mode"), None)
    if mode is None and len(call.args) > position:
        mode = call.args[position]
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(WRITING_MODES & set(mode.value))
    # A mode not written out can't be read here, so it counts.
    return True


def writes(source: str) -> list[str]:
    """Each call in a module's source that changes a file: its name."""
    found = []
    imported: dict[str, str] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module in (
            *CHANGING_FUNCTIONS,
            *READING,
        ):
            for alias in node.names:
                if _changes(node.module, alias.name):
                    imported[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in imported:
                found.append(imported[func.id])
            elif func.id == "open" and _mode_writes(node, 1):
                found.append("open")
            continue
        if not isinstance(func, ast.Attribute):
            continue
        base = _dotted(func.value)
        if base in CHANGING_FUNCTIONS or base in READING:
            if _changes(base, func.attr):
                found.append(f"{base}.{func.attr}")
        elif func.attr in CHANGING_METHODS:
            found.append(func.attr)
        elif func.attr == "open" and _mode_writes(node, 1 if base == "io" else 0):
            found.append(name or "open")
    return found


def modules() -> list[Path]:
    return sorted(SOURCE.rglob("*.py"))


def test_only_the_executor_and_the_named_writers_change_files():
    found = []
    for path in modules():
        module = path.relative_to(SOURCE).as_posix()
        if module in WRITERS:
            continue
        for call in writes(path.read_text()):
            if (module, call) not in EXCEPTIONS:
                found.append(f"{module}: {call}")
    assert found == []


def test_every_exception_is_still_needed():
    found = {
        (path.relative_to(SOURCE).as_posix(), call)
        for path in modules()
        for call in writes(path.read_text())
    }
    assert EXCEPTIONS <= found
    assert all((SOURCE / module).exists() for module in WRITERS)


@pytest.mark.parametrize(
    ("source", "call"),
    [
        ("open(p, 'w')", "open"),
        ("open(p, mode='ab')", "open"),
        ("open(p, m)", "open"),
        ("path.open('r+')", "path.open"),
        ("path.write_bytes(b'')", "write_bytes"),
        ("self.root.joinpath(n).mkdir()", "mkdir"),
        ("p.rename(q)", "rename"),
        ("os.replace(p, q)", "os.replace"),
        ("os.open(p, os.O_RDONLY)", "os.open"),
        ("shutil.move(p, q)", "shutil.move"),
        ("shutil.copy2(p, q)", "shutil.copy2"),
        ("from os import remove\nremove(p)", "os.remove"),
        ("from shutil import rmtree as gone\ngone(p)", "shutil.rmtree"),
        ("sqlite3.connect(p)", "sqlite3.connect"),
        ("tempfile.NamedTemporaryFile(dir=p)", "tempfile.NamedTemporaryFile"),
    ],
)
def test_the_scan_finds_a_module_that_writes(source, call):
    assert writes(source) == [call]


@pytest.mark.parametrize(
    "source",
    [
        "open(p)",
        "open(p, 'rb')",
        "path.open()",
        "text.replace('a', 'b')",
        "names.remove(x)",
        "shutil.which('ffprobe')",
        "os.stat(p)",
    ],
)
def test_the_scan_passes_what_only_reads(source):
    assert writes(source) == []


# The runtime half, exercised: a module made to write under a guarded root is
# caught, and the executor and the exporter, in its own folder, are not.


def test_a_module_writing_under_the_root_is_caught(tmp_path, monkeypatch):
    root = tmp_path / "video"
    root.mkdir()
    monkeypatch.setattr(manifest, "SCHEMA_FILE", root / "movies.json")
    made = share_guard.guard(root)
    try:
        manifest.write_schema()
    finally:
        violations = share_guard.release(made)
    assert violations and all(v.startswith("manifest.py: ") for v in violations)


def test_the_same_write_outside_the_root_is_not(tmp_path, monkeypatch):
    root = tmp_path / "video"
    root.mkdir()
    monkeypatch.setattr(manifest, "SCHEMA_FILE", tmp_path / "schema.json")
    made = share_guard.guard(root)
    try:
        manifest.write_schema()
    finally:
        assert share_guard.release(made) == []


def test_the_executor_writes_under_the_root(tmp_path, guarded):
    root = tmp_path / "video"
    root.mkdir()
    guarded(root)
    writer = Writer(root, dry_run=False)
    writer.make_folder("movies")
    writer.write("movies/movie.nfo", b"<movie/>")
    assert (root / "movies" / "movie.nfo").read_bytes() == b"<movie/>"


def test_the_exporter_writes_in_its_own_folder_and_nowhere_else(tmp_path):
    from reelbarrow.exporter import write_atomically

    root = tmp_path / "video"
    out = root / "import" / "manifests"
    out.mkdir(parents=True)
    made = share_guard.guard(root)
    made.allow("exporter.py", out)
    try:
        write_atomically(out, "manifest-arm-1-1.json", json.dumps({}).encode())
        write_atomically(root, "manifest-arm-1-1.json", json.dumps({}).encode())
    finally:
        violations = share_guard.release(made)
    assert violations
    assert all(str(out) not in v for v in violations)
