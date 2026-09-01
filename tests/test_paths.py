import os

from app.utils.paths import (
    ensure_remote_dir_suffix,
    get_downloads_directory,
    get_windows_username,
    is_valid_local_path,
    is_valid_remote_path,
    remote_basename,
    remote_home_directory,
    remote_join,
    remote_parent,
)


def test_valid_windows_paths():
    assert is_valid_local_path(r"C:\Users\Alice\Documents\report.pdf")
    assert is_valid_local_path(r"D:\backup.zip")


def test_invalid_windows_paths():
    assert not is_valid_local_path("")
    assert not is_valid_local_path("   ")
    assert not is_valid_local_path("C:\\Users\\Alice\\bad<name>.txt")
    assert not is_valid_local_path("C:\\Users\\Alice\\bad|name.txt")


def test_valid_remote_paths():
    assert is_valid_remote_path("/home/alice/Documents/report.pdf")
    assert is_valid_remote_path("/home/alice/")


def test_invalid_remote_paths():
    assert not is_valid_remote_path("")
    assert not is_valid_remote_path("   ")


def test_remote_home_directory():
    assert remote_home_directory("alice") == "/home/alice/"


def test_remote_join_uses_posix_semantics():
    assert remote_join("/home/alice", "Documents", "report.pdf") == "/home/alice/Documents/report.pdf"


def test_remote_parent():
    assert remote_parent("/home/alice/Documents/report.pdf") == "/home/alice/Documents/"
    assert remote_parent("/home/alice/") == "/home/"


def test_remote_basename():
    assert remote_basename("/home/alice/Documents/report.pdf") == "report.pdf"


def test_ensure_remote_dir_suffix():
    assert ensure_remote_dir_suffix("/home/alice") == "/home/alice/"
    assert ensure_remote_dir_suffix("/home/alice/") == "/home/alice/"


def test_get_windows_username_returns_nonempty_string(monkeypatch):
    monkeypatch.setenv("USERNAME", "Alice")
    assert get_windows_username() == "Alice"


def test_get_downloads_directory_uses_userprofile(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    downloads = get_downloads_directory()
    assert str(downloads) == str(tmp_path / "Downloads")
