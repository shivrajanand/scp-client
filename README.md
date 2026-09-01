# SCP Transfer Client

A modern, lightweight desktop SCP client for **Windows** for transferring
individual files between your Windows PC and Linux servers — without
memorizing SCP command syntax.

## 1. What it does

- **Send to Server** — upload a file from Windows to a Linux server.
- **Fetch from Server** — download a file from a Linux server to Windows.
- Loads servers automatically from your existing SSH config, and/or lets
  you manage a separate list of servers through the GUI.
- Prompts for a password at connect time — **passwords are never stored**.
- Lets you browse the remote filesystem to pick a file for download.
- Shows explicit local and remote paths (never a bare `~/`).
- Shows transfer progress, speed, ETA, and status, with an activity log.
- Only handles **single files** — no directory sync, no recursive
  transfer. Zip a folder first if you need to move one.

## 2. Supported operating systems

- **Runtime target:** Windows 10 / 11 (this is what the packaged `.exe` is
  built and tested for).
- **Remote servers:** any Linux server with an SSH server (SCP/SFTP
  capable).
- The Python source itself is cross-platform and can also be run on macOS
  or Linux for development purposes, though the packaged executable and
  default paths (Downloads folder, `%APPDATA%`) are Windows-oriented.

## 3. Python version

Python 3.10 or newer is recommended for development.

## 4. Installation

### Option A — Run the packaged executable (end users)

1. Download or build `SCPTransferClient.exe` (see [Building the Windows
   executable](#15-building-the-windows-executable)).
2. Double-click it. No Python installation is required.

### Option B — Run from source (developers)

```powershell
git clone <this-repo-url>
cd scp-client
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 5. Dependency installation

Runtime dependencies are listed in `requirements.txt`:

```text
PySide6
paramiko
scp
```

Install them with:

```powershell
pip install -r requirements.txt
```

For development (tests + packaging), install `requirements-dev.txt`
instead, which also pulls in `pytest` and `pyinstaller`.

## 6. Running from source

```powershell
python main.py
```

This launches the GUI directly with no console window management needed
during development (a console will be attached when run this way; the
packaged `.exe` is built windowless — see below).

## 7. SSH config usage

On startup (and whenever the server list is refreshed), the app reads:

```text
%USERPROFILE%\.ssh\config
```

and exposes each `Host` entry with a `HostName`, `User`, and (optionally)
`Port` as a selectable server in the dropdown, grouped under **SSH
Config**. Example:

```text
Host production
    HostName 192.168.1.100
    User alice
    Port 22
```

shows up as **production** in the server list. Hosts without a `User`
directive are skipped, since the app has no way to guess a username for
them.

Known-hosts information is read from:

```text
%USERPROFILE%\.ssh\known_hosts
```

to support host-key verification (see below).

## 8. Manual server configuration

Servers that aren't in your SSH config can be added through **⚙ Servers**
in the main window. Each manual server has a name, hostname/IP, username,
and port — but deliberately **no password field**. Manual servers are
grouped under **Saved Servers** in the dropdown and are stored in:

```text
%APPDATA%\SCPTransferClient\servers.json
```

You can add, edit, delete, enable/disable, and test-connect servers from
the Server Manager dialog.

## 9. Password behavior

- You are prompted for a password each time a connection is made that
  requires one — passwords are **never written to disk**, never included
  in `servers.json` / `config.json`, never logged, and never shown in
  plain text.
- The password is held only in memory for the duration of the connection
  attempt and is discarded as soon as the connection is established or
  fails.

## 10. Upload workflow

1. Click **Send to Server**.
2. Select a server.
3. Click **Browse...** to pick a local file.
4. Confirm or edit the remote destination directory (defaults to the
   remote user's home directory, shown as an explicit path like
   `/home/alice/`, not `~/`).
5. Click **TRANSFER**.
6. Enter the password if prompted.
7. Watch progress, speed, and ETA update live; check the activity log for
   a step-by-step record.

## 11. Download workflow

1. Click **Fetch from Server**.
2. Select a server.
3. Click **Browse Remote...** to open the remote file browser, navigate,
   and pick a file.
4. Confirm or change the local destination folder (defaults to
   `C:\Users\<YourUsername>\Downloads\`).
5. Click **TRANSFER**.
6. Enter the password if prompted.
7. Watch progress; you'll be asked to confirm before an existing local
   file is overwritten.

## 12. Remote browser

The remote file browser (used when picking a download source, or when
picking an upload destination directory) is **read-only**: it can list
directories, navigate into and out of them, refresh, and select a file.
It intentionally has no delete, rename, move, chmod/chown, or shell
functionality — its only job is helping you find the right path.

## 13. Host-key verification

The app does **not** blindly trust unknown host keys:

- Known hosts are checked against `%USERPROFILE%\.ssh\known_hosts`.
- If a host's key is unknown, you'll see a dialog with the server's
  fingerprint and can choose **Trust Once** (this session only) or
  **Trust & Save** (adds it to `known_hosts`), or cancel the connection.
- If a host's key has **changed** since it was last trusted, the app
  shows an explicit warning (a possible sign of a man-in-the-middle
  attack) before allowing you to proceed — nothing is auto-trusted in
  this case.

## 14. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "Unable to connect to host:port" | Check network connectivity, that the SSH server is running, and that the port/firewall allow the connection. |
| "Authentication failed" | Double-check username and password. Key-based auth beyond an SSH-config `IdentityFile` isn't a first-class flow in v1. |
| Server doesn't appear in the dropdown | For SSH-config servers, confirm the `Host` block has a `User` directive. For manual servers, check they're **enabled** in the Server Manager. |
| "Permission denied" during transfer | The remote/local user doesn't have write access to that path — pick a different destination. |
| Host key warnings on every connection | You chose "Trust Once" instead of "Trust & Save"; choose "Trust & Save" to persist the key to `known_hosts`. |
| App won't launch after building the `.exe` | Rebuild with `--windowed` removed temporarily to see console errors, or check `%APPDATA%\SCPTransferClient\scp_client.log`. |

## 15. Building the Windows executable

From the project root, with `requirements-dev.txt` installed:

```powershell
pyinstaller build\scp-client.spec
```

This uses the provided `.spec` file (rather than a bare `pyinstaller
main.py` invocation) so that the `assets/` folder is bundled and the
build stays reproducible. It produces:

```text
dist\SCPTransferClient\SCPTransferClient.exe
```

built with `console=False`, so it launches without a console window. For
a quick one-off build without the spec file:

```powershell
pyinstaller --windowed --name SCPTransferClient main.py
```

Test the resulting executable on a clean Windows machine/VM (without your
development Python environment) before distributing it.

## 16. Security notes

- **Passwords are never persisted** — not in JSON config, not in the
  Windows registry, not in logs, not in crash output.
- Password fields in the GUI are always masked.
- The activity log and application log file pass through a redacting
  filter that scrubs anything resembling `password: ...`, as defense in
  depth on top of simply never logging credentials.
- SSH traffic is encrypted end-to-end via Paramiko's SSH implementation.
- Host-key verification is never silently disabled; unknown or changed
  keys always require an explicit decision from you.
- The remote browser is read-only — the app cannot delete, modify, or
  execute anything on the remote server.
- This is a **single-file transfer tool** by design — no directory sync,
  no recursive transfer, no FTP/FTPS/rsync, keeping the attack surface
  and complexity small.

## Project structure

```text
scp-client/
├── main.py                  # entry point
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── LICENSE
├── app/
│   ├── gui/                 # PySide6 windows/dialogs
│   ├── ssh/                 # SSH config parsing, connection, host keys
│   ├── transfer/            # SCP transfer + background worker + progress
│   ├── config/               # data models + JSON persistence
│   └── utils/                # path + logging helpers
├── tests/                    # pytest test suite
├── assets/icons/              # app icon (place app.ico here for the .exe)
└── build/scp-client.spec      # PyInstaller build spec
```

## Running tests

```powershell
pip install -r requirements-dev.txt
pytest
```

## Roadmap / explicitly out of scope for v1

Directory sync, recursive folder transfer, FTP/FTPS/rsync, an
SSH/terminal shell, server administration, in-app file editing,
multi-server parallel transfers, password storage, cloud credential
storage, network auto-discovery, and compression are all intentionally
**not** part of version 1. See `SCP_Transfer_Client_Project_Specification.md`
for the full project spec, including a list of possible future additions
(drag-and-drop, transfer history, SFTP mode, SSH key auth, etc.) that the
architecture is intended to accommodate without a rewrite.
