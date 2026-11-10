"""The runtime half of the rule that only the executor changes the video root
(*Rules that protect the library*, in `AGENTS.md`).

An audit hook (PEP 578) sees every open for writing, rename, removal, folder
made and attribute changed in the test process. A change under a guarded root
is the program's when the innermost frame that made it is in reelbarrow's own
source, and it is allowed only from `reelbarrow/executor.py`, or from a module
given a folder of its own, as the exporter is given its `--out`. A change the
tests make, building a share, is the world's and isn't judged.

The static half, `test_write_guard.py`, reads every module for the calls that
write; this half catches the ones it can't see, such as a library writing on
a module's behalf.
"""

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import reelbarrow

SOURCE = Path(reelbarrow.__file__).resolve().parent
EXECUTOR = SOURCE / "executor.py"

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
# Events whose first argument is the path changed.
_ONE_PATH = frozenset(
    {
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.chmod",
        "os.chown",
        "os.chflags",
        "os.utime",
        "os.truncate",
        "os.setxattr",
        "os.removexattr",
        "shutil.rmtree",
        "sqlite3.connect",
    }
)
# Events whose first two arguments are paths, both changed or made.
_TWO_PATHS = frozenset(
    {
        "os.rename",
        "os.link",
        "os.symlink",
        "shutil.copyfile",
        "shutil.copymode",
        "shutil.copystat",
        "shutil.copytree",
        "shutil.move",
    }
)


@dataclass
class Guard:
    root: str
    # (module's source file, folder it may write in)
    allowed: list[tuple[Path, str]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def allow(self, module: str, folder: Path) -> None:
        """Lets one of reelbarrow's modules write in one folder."""
        self.allowed.append((SOURCE / module, os.path.abspath(folder)))

    def holds(self, path: str) -> bool:
        return _within(path, self.root)


_guards: list[Guard] = []
_busy = threading.local()


def _within(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([path, folder]) == folder
    except ValueError:
        return False


def _paths(event: str, args: tuple) -> list[object]:
    if event == "open":
        path, mode, flags = args
        writes = (
            any(c in mode for c in "wax+")
            if isinstance(mode, str)
            else bool(flags & _WRITE_FLAGS)
        )
        return [path] if writes else []
    if event in _ONE_PATH:
        return [args[0]]
    if event in _TWO_PATHS:
        return [args[0], args[1]]
    return []


def _writer() -> Path | None:
    """The source file of reelbarrow's innermost frame on the stack."""
    frame = sys._getframe(2)
    while frame is not None:
        filename = Path(frame.f_code.co_filename)
        if filename.is_relative_to(SOURCE):
            return filename
        frame = frame.f_back
    return None


def _hook(event: str, args: tuple) -> None:
    if not _guards or getattr(_busy, "on", False):
        return
    paths = _paths(event, args)
    if not paths:
        return
    _busy.on = True
    try:
        for raw in paths:
            if isinstance(raw, int) or raw is None:
                continue
            text = os.fsdecode(raw)
            if text.startswith("file:"):
                # sqlite3's URI form.
                text = text.removeprefix("file:").split("?")[0]
            path = os.path.abspath(text)
            for guard in _guards:
                if not guard.holds(path):
                    continue
                writer = _writer()
                if writer is None or writer == EXECUTOR:
                    continue
                if any(
                    writer == module and _within(path, folder)
                    for module, folder in guard.allowed
                ):
                    continue
                guard.violations.append(f"{writer.name}: {event} {path}")
    finally:
        _busy.on = False


sys.addaudithook(_hook)


def guard(root: Path) -> Guard:
    """Guards a root until `release`; its violations are checked there."""
    made = Guard(root=os.path.abspath(root))
    _guards.append(made)
    return made


def release(made: Guard) -> list[str]:
    _guards.remove(made)
    return made.violations
