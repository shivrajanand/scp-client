import json

import pytest

from app.config.manager import ConfigError, ConfigManager
from app.config.models import AppPreferences, Server, ServerSource


@pytest.fixture
def config_manager(tmp_path):
    return ConfigManager(app_data_dir=tmp_path)


def test_load_servers_returns_empty_list_when_missing(config_manager):
    assert config_manager.load_servers() == []


def test_save_and_load_servers_round_trip(config_manager):
    servers = [
        Server(name="Production", hostname="192.168.1.100", username="alice", port=22),
        Server(name="Dev", hostname="dev.example.com", username="bob", port=2222),
    ]
    config_manager.save_servers(servers)

    loaded = config_manager.load_servers()
    assert len(loaded) == 2
    assert loaded[0].name == "Production"
    assert loaded[0].hostname == "192.168.1.100"
    assert loaded[0].source == ServerSource.MANUAL


def test_save_servers_never_writes_password_field(config_manager, tmp_path):
    servers = [Server(name="Production", hostname="host", username="alice", port=22)]
    config_manager.save_servers(servers)

    raw = json.loads(config_manager.servers_path.read_text(encoding="utf-8"))
    dumped_text = json.dumps(raw)
    assert "password" not in dumped_text.lower()


def test_save_servers_excludes_ssh_config_servers(config_manager):
    manual = Server(name="Manual", hostname="h1", username="u1", source=ServerSource.MANUAL)
    from_ssh = Server(name="FromConfig", hostname="h2", username="u2", source=ServerSource.SSH_CONFIG)
    config_manager.save_servers([manual, from_ssh])

    loaded = config_manager.load_servers()
    assert len(loaded) == 1
    assert loaded[0].name == "Manual"


def test_add_edit_delete_server_workflow(config_manager):
    servers = [Server(name="A", hostname="h", username="u")]
    config_manager.save_servers(servers)

    # Add
    servers.append(Server(name="B", hostname="h2", username="u2"))
    config_manager.save_servers(servers)
    assert {s.name for s in config_manager.load_servers()} == {"A", "B"}

    # Edit
    servers[0].hostname = "h-updated"
    config_manager.save_servers(servers)
    loaded = {s.name: s for s in config_manager.load_servers()}
    assert loaded["A"].hostname == "h-updated"

    # Delete
    servers = [s for s in servers if s.name != "B"]
    config_manager.save_servers(servers)
    assert {s.name for s in config_manager.load_servers()} == {"A"}


def test_load_servers_rejects_invalid_json(config_manager):
    config_manager.app_data_dir.mkdir(parents=True, exist_ok=True)
    config_manager.servers_path.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(ConfigError):
        config_manager.load_servers()


def test_load_servers_skips_invalid_entries(config_manager):
    config_manager.app_data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "servers": [
            {"name": "Good", "hostname": "h", "username": "u", "port": 22},
            {"name": "MissingHostname", "username": "u"},
        ]
    }
    config_manager.servers_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = config_manager.load_servers()
    assert len(loaded) == 1
    assert loaded[0].name == "Good"


def test_preferences_round_trip(config_manager):
    prefs = AppPreferences(theme="light", last_server_name="Production")
    config_manager.save_preferences(prefs)

    loaded = config_manager.load_preferences()
    assert loaded.theme == "light"
    assert loaded.last_server_name == "Production"


def test_preferences_defaults_when_missing(config_manager):
    prefs = config_manager.load_preferences()
    assert prefs.theme == "dark"
    assert prefs.last_server_name is None


def test_server_from_dict_rejects_bad_port():
    with pytest.raises(ValueError):
        Server.from_dict({"name": "X", "hostname": "h", "username": "u", "port": "not-a-number"})


def test_server_from_dict_requires_fields():
    with pytest.raises(ValueError):
        Server.from_dict({"name": "X"})
