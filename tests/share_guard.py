"""The runtime half of the rule that only the executor changes the video root
(*Rules that protect the library*, in `AGENTS.md`).

An audit hook (PEP 578) sees every open for writing, rename, removal, folder
made and attribute changed in the test process. A change under a guarded root
is the program's when the innermost frame that made it is in reelbarrow's own
source, and it is allowed only from `reelbarrow/executor.py`, or from a module
given a folder of its own, as the exporter is given its `--out`. A change the
tests make, building a share, is the world's and isn't judged.

A tool's writes are its own process's, which no hook here sees, so a tool is
judged by its command as it starts: one of reelbarrow's modules other than
the executor, starting one that isn't among `READING_TOOLS`, or ffmpeg with a
command `ffmpeg_writes` finds could write a file, while a root is guarded, is
a violation of every guard.

The static half, `test_write_guard.py`, reads every module for the calls that
write; this half catches the ones it can't see, such as a library writing on
a module's behalf.
"""

import os
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import reelbarrow

SOURCE = Path(reelbarrow.__file__).resolve().parent
EXECUTOR = SOURCE / "executor.py"

# The tools a module other than the executor may run: the analysis's
# measures, which read the files they are given. ffmpeg also writes, so its
# command is judged too (`ffmpeg_writes`).
READING_TOOLS = frozenset({"ffprobe", "ffmpeg", "fpcalc", "lsdvd"})

# ffmpeg's options the analysis gives it, each with whether it takes a value.
# ffmpeg writes a file only where its command names one: as an output, or as
# the value of an option such as -report, -progress or -vstats_file. So a
# command made only of these, whose one output is `-`, writes only to its
# stdout. An option added here must be one that names no file it writes.
FFMPEG_OPTIONS = {
    "-nostdin": False,
    "-v": True,
    "-i": True,
    "-map": True,
    "-c": True,
    "-ac": True,
    "-ar": True,
    "-f": True,
}
# Formats that write the stream they are given to the output and nowhere
# else. Some don't: hls and segment write files named after it.
FFMPEG_FORMATS = frozenset({"md5", "s16le"})


def ffmpeg_writes(args: Sequence[str | None]) -> str | None:
    """What in an ffmpeg command could make it write a file, or None when it
    writes only to its stdout. `args` are the words after `ffmpeg`; None
    stands for one the source doesn't spell out, which could be anything.

    It doesn't see the environment, where FFREPORT has ffmpeg write a log
    into its working directory; reelbarrow never sets it."""
    if not args or args[-1] != "-":
        return "to an output other than its stdout"
    words = iter(args[:-1])
    for word in words:
        if word is None:
            return "with a word not written out"
        if word not in FFMPEG_OPTIONS:
            return f"with {word}"
        if not FFMPEG_OPTIONS[word]:
            continue
        value = next(words, None)
        if word == "-f" and value not in FFMPEG_FORMATS:
            return f"with -f {value or 'unknown'}"
    return None


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


def _command(command: object) -> list[str]:
    if isinstance(command, str | bytes | os.PathLike):
        # A shell's command line, or a program with no arguments.
        return os.fsdecode(command).split()
    return [os.fsdecode(word) for word in command]  # type: ignore[attr-defined]


def _started(args: tuple) -> None:
    """`subprocess.Popen`'s event: (executable, args, cwd, env)."""
    command = _command(args[1])
    program = os.path.basename(command[0]) if command else ""
    why = ffmpeg_writes(command[1:]) if program == "ffmpeg" else None
    if program in READING_TOOLS and why is None:
        return
    writer = _writer()
    if writer is None or writer == EXECUTOR:
        return
    ran = program if why is None else f"{program}, {why}"
    for guard in _guards:
        guard.violations.append(f"{writer.name}: ran {ran}")


def _hook(event: str, args: tuple) -> None:
    if not _guards or getattr(_busy, "on", False):
        return
    if event == "subprocess.Popen":
        _busy.on = True
        try:
            _started(args)
        finally:
            _busy.on = False
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
