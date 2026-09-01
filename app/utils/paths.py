"""
Path handling helpers.

Windows (local) paths and Linux (remote) paths are handled with
completely separate logic, per project spec section 36. Never mix
`pathlib.PureWindowsPath`/`os.path` local logic with remote POSIX paths.
"""

from __future__ import annotations

import getpass
import os
import re
from pathlib import Path, PureWindowsPath, PurePosixPath


# ---------------------------------------------------------------------------
# Local (Windows) paths
# ---------------------------------------------------------------------------

def get_windows_username() -> str:
    """Best-effort detection of the current Windows username."""
    for var in ("USERNAME", "USER"):
        value = os.environ.get(var)
        if value:
            return value
    try:
        return getpass.getuser()
    except Exception:
        return "User"


def get_downloads_directory() -> Path:
    """Return the current user's Downloads directory.

    Uses USERPROFILE on Windows; falls back to the home directory with a
    'Downloads' subfolder so the app remains testable off-Windows.
    """
    userprofile = os.environ.get("USERPROFILE")
    base = Path(userprofile) if userprofile else Path.home()
    downloads = base / "Downloads"
    return downloads


def is_valid_local_path(path: str) -> bool:
    """Very defensive syntactic validation of a local (Windows) path string.

    This does not check existence -- only that the string is a plausible
    path (non-empty, no forbidden characters in the filename portion).
    """
    if not path or not path.strip():
        return False

    # Reserved characters that are illegal anywhere in a Windows path
    # component (aside from the drive-letter colon and path separators).
    forbidden = set('<>"|?*')
    # Strip a leading drive letter (e.g. "C:") before checking for stray colons.
    body = path
    if re.match(r"^[A-Za-z]:", body):
        body = body[2:]
    if ":" in body:
        return False
    if any(ch in forbidden for ch in body):
        return False
    return True


def local_display_path(path: os.PathLike | str) -> str:
    """Render a local path the way Windows Explorer would (backslashes)."""
    return str(PureWindowsPath(str(path)))


# ---------------------------------------------------------------------------
# Remote (Linux / POSIX) paths
# ---------------------------------------------------------------------------

_POSIX_FORBIDDEN_CHARS = "\x00"


def is_valid_remote_path(path: str) -> bool:
    """Syntactic validation of a remote POSIX path string."""
    if not path or not path.strip():
        return False
    if any(ch in _POSIX_FORBIDDEN_CHARS for ch in path):
        return False
    return True


def remote_home_directory(username: str) -> str:
    """Construct a best-guess remote home directory before authentication.

    The real home directory is resolved after connecting (via `pwd`/SFTP
    normalize) when possible; this is only the initial default shown in
    the GUI, per spec section 8.
    """
    return f"/home/{username}/"


def remote_join(base: str, *parts: str) -> str:
    """Join POSIX path components using PurePosixPath, never os.path."""
    result = PurePosixPath(base)
    for part in parts:
        result = result / part
    return str(result)


def remote_parent(path: str) -> str:
    """Return the parent directory of a remote path, POSIX-style."""
    p = PurePosixPath(path)
    parent = p.parent
    text = str(parent)
    if not text.endswith("/"):
        text += "/"
    return text


def remote_basename(path: str) -> str:
    return PurePosixPath(path).name


def ensure_remote_dir_suffix(path: str) -> str:
    """Ensure a remote directory path ends with a trailing slash for display."""
    if not path.endswith("/"):
        return path + "/"
    return path
