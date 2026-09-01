from unittest.mock import MagicMock, patch

import pytest
from scp import SCPException

from app.config.models import Server, ServerSource
from app.ssh.connection import ConnectionError_, SSHConnection
from app.transfer.progress import ProgressTracker, format_bytes, format_eta, format_speed
from app.transfer.scp_client import ScpFileTransfer, TransferCancelled, TransferError


@pytest.fixture
def fake_server():
    return Server(name="Test", hostname="example.com", username="alice", port=22, source=ServerSource.MANUAL)


@pytest.fixture
def fake_connection(fake_server):
    conn = SSHConnection(fake_server)
    conn._client = MagicMock()
    conn._sftp = MagicMock()
    conn.connected = True
    return conn


class FakeSCPClient:
    """Stand-in for scp.SCPClient used to avoid any real network I/O."""

    instances = []

    def __init__(self, transport, progress=None):
        self.transport = transport
        self.progress = progress
        self.put_calls = []
        self.get_calls = []
        FakeSCPClient.instances.append(self)

    def put(self, local_path, remote_path=None):
        self.put_calls.append((local_path, remote_path))
        if self.progress:
            self.progress(remote_path, 100, 50)
            self.progress(remote_path, 100, 100)

    def get(self, remote_path, local_path=None):
        self.get_calls.append((remote_path, local_path))
        # Simulate the download by actually creating the local file so
        # existence checks pass, without touching the network.
        with open(local_path, "wb") as fh:
            fh.write(b"x" * 100)
        if self.progress:
            self.progress(remote_path, 100, 100)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def reset_fake_scp():
    FakeSCPClient.instances.clear()
    yield
    FakeSCPClient.instances.clear()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_request_calls_scp_put(fake_connection, tmp_path):
    local_file = tmp_path / "report.pdf"
    local_file.write_bytes(b"hello world")

    with patch("app.transfer.scp_client.SCPClient", FakeSCPClient):
        transfer = ScpFileTransfer(fake_connection)
        result = transfer.upload(str(local_file), "/home/alice/Documents")

    assert result == "/home/alice/Documents/report.pdf"
    assert FakeSCPClient.instances[0].put_calls[0][1] == "/home/alice/Documents/report.pdf"


def test_upload_missing_local_file_raises(fake_connection, tmp_path):
    missing = tmp_path / "missing.txt"
    transfer = ScpFileTransfer(fake_connection)
    with pytest.raises(TransferError):
        transfer.upload(str(missing), "/home/alice/")


def test_upload_reports_progress(fake_connection, tmp_path):
    local_file = tmp_path / "report.pdf"
    local_file.write_bytes(b"hello world")

    events = []
    with patch("app.transfer.scp_client.SCPClient", FakeSCPClient):
        transfer = ScpFileTransfer(fake_connection)
        transfer.upload(
            str(local_file), "/home/alice/Documents",
            progress_callback=lambda name, sent, total: events.append((name, sent, total)),
        )

    assert len(events) == 2
    assert events[-1] == ("report.pdf", 100, 100)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def test_download_request_calls_scp_get(fake_connection, tmp_path):
    fake_connection.sftp.stat = MagicMock(return_value=object())

    dest_dir = tmp_path / "downloads"
    with patch("app.transfer.scp_client.SCPClient", FakeSCPClient):
        transfer = ScpFileTransfer(fake_connection)
        result = transfer.download("/home/alice/Documents/report.pdf", str(dest_dir))

    assert result == str(dest_dir / "report.pdf")
    assert (dest_dir / "report.pdf").exists()


def test_download_missing_remote_file_raises(fake_connection, tmp_path):
    fake_connection.sftp.stat = MagicMock(side_effect=FileNotFoundError())

    transfer = ScpFileTransfer(fake_connection)
    with pytest.raises(TransferError):
        transfer.download("/home/alice/missing.txt", str(tmp_path))


# ---------------------------------------------------------------------------
# Authentication / connection failures (mocked at the connection layer)
# ---------------------------------------------------------------------------

def test_authentication_failure_message(fake_server):
    import paramiko
    from app.ssh.connection import AuthenticationFailedError

    conn = SSHConnection(fake_server)
    with patch("paramiko.SSHClient") as MockClient:
        instance = MockClient.return_value
        instance.connect.side_effect = paramiko.AuthenticationException()
        with pytest.raises(AuthenticationFailedError):
            conn.connect(password="wrong-password")


def test_connection_failure_message(fake_server):
    conn = SSHConnection(fake_server)
    with patch("paramiko.SSHClient") as MockClient:
        instance = MockClient.return_value
        instance.connect.side_effect = OSError("network unreachable")
        with pytest.raises(ConnectionError_):
            conn.connect(password="whatever")


# ---------------------------------------------------------------------------
# Permission failure
# ---------------------------------------------------------------------------

def test_upload_permission_denied(fake_connection, tmp_path):
    local_file = tmp_path / "report.pdf"
    local_file.write_bytes(b"data")

    class DenyingSCPClient(FakeSCPClient):
        def put(self, local_path, remote_path=None):
            raise PermissionError("denied")

    with patch("app.transfer.scp_client.SCPClient", DenyingSCPClient):
        transfer = ScpFileTransfer(fake_connection)
        with pytest.raises(TransferError):
            transfer.upload(str(local_file), "/root/")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def test_upload_cancellation_raises(fake_connection, tmp_path):
    local_file = tmp_path / "report.pdf"
    local_file.write_bytes(b"data" * 1000)

    with patch("app.transfer.scp_client.SCPClient", FakeSCPClient):
        transfer = ScpFileTransfer(fake_connection)
        transfer.cancel()
        with pytest.raises(TransferCancelled):
            transfer.upload(str(local_file), "/home/alice/")


# ---------------------------------------------------------------------------
# Progress tracker
# ---------------------------------------------------------------------------

def test_progress_tracker_percent():
    tracker = ProgressTracker("file.bin")
    snapshot = tracker.update(50, 100)
    assert snapshot.percent == 50.0


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert "KB" in format_bytes(2048)


def test_format_eta_infinite():
    assert format_eta(float("inf")) == "--:--"


def test_format_speed_contains_unit():
    assert "/s" in format_speed(1024)
