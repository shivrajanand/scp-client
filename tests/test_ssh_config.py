import pytest

from app.config.models import ServerSource
from app.ssh.config_loader import load_ssh_config_servers


SAMPLE_CONFIG = """
Host production
    HostName 192.168.1.100
    User alice
    Port 22

Host development
    HostName dev.example.com
    User bob
    Port 2222

Host no-user
    HostName 10.0.0.5

Host *
    ServerAliveInterval 60
"""


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config"
    path.write_text(SAMPLE_CONFIG, encoding="utf-8")
    return path


def test_parses_multiple_hosts(config_file):
    servers = load_ssh_config_servers(config_file)
    names = {s.name for s in servers}
    assert "production" in names
    assert "development" in names


def test_extracts_username_hostname_port(config_file):
    servers = {s.name: s for s in load_ssh_config_servers(config_file)}
    prod = servers["production"]
    assert prod.hostname == "192.168.1.100"
    assert prod.username == "alice"
    assert prod.port == 22

    dev = servers["development"]
    assert dev.hostname == "dev.example.com"
    assert dev.username == "bob"
    assert dev.port == 2222


def test_defaults_port_to_22_when_unspecified(tmp_path):
    path = tmp_path / "config"
    path.write_text("Host simple\n    HostName example.com\n    User carol\n", encoding="utf-8")
    servers = load_ssh_config_servers(path)
    assert servers[0].port == 22


def test_skips_hosts_without_user(config_file):
    servers = load_ssh_config_servers(config_file)
    names = {s.name for s in servers}
    assert "no-user" not in names


def test_wildcard_host_is_not_a_server(config_file):
    servers = load_ssh_config_servers(config_file)
    names = {s.name for s in servers}
    assert "*" not in names


def test_servers_have_ssh_config_source(config_file):
    servers = load_ssh_config_servers(config_file)
    assert all(s.source == ServerSource.SSH_CONFIG for s in servers)


def test_handles_missing_config_file(tmp_path):
    missing_path = tmp_path / "does-not-exist"
    servers = load_ssh_config_servers(missing_path)
    assert servers == []
