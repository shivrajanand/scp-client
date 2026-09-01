# SCP Transfer Client for Windows

## 1. Project Overview

A modern, lightweight desktop SCP client for **Windows** that makes it easy to transfer individual files between a Windows host PC and Linux servers.

The application will provide two simple operations:

1. **Send to Server** — upload a file from Windows to a Linux server.
2. **Fetch from Server** — download a file from a Linux server to Windows.

The application will support two ways of defining servers:

- Automatically load servers from the user's existing SSH configuration.
- Maintain a separate list of manually configured servers through the GUI.

Passwords will **never be stored**. When password authentication is required, the application will prompt the user at connection time.

---

# 2. Project Objectives

The primary objectives are:

- Provide a simple GUI for SCP file transfers.
- Make upload/download direction immediately obvious.
- Avoid requiring users to manually construct complicated SCP commands.
- Reuse the user's existing SSH configuration where possible.
- Allow manually managed server definitions when SSH config is not appropriate.
- Support password-based authentication without persisting passwords.
- Allow remote filesystem browsing for easier file selection.
- Display explicit local and remote paths.
- Show transfer progress, speed, ETA, and status.
- Provide useful, human-readable error messages.
- Keep the application lightweight and focused on **single-file transfers**.
- Package the application so it can be distributed as a Windows executable.

---

# 3. Scope

## 3.1 In Scope

### File Transfers

- Windows → Linux upload.
- Linux → Windows download.
- Individual files only.
- User-selected destination paths.
- Transfer progress.
- Transfer status.
- Transfer error handling.

### Server Sources

- Windows OpenSSH configuration.
- Manually configured servers.
- Server management through GUI.

### Authentication

- Username.
- Password authentication.
- Password prompt at connection time.
- No password persistence.

### Remote File Navigation

- Browse remote directories.
- Navigate into directories.
- Navigate to parent directories.
- Refresh directory contents.
- Select a remote file for download.

### Local File Navigation

- Windows file selection dialog.
- Windows folder selection dialog.
- Default Downloads location for downloads.

### GUI

- Modern desktop interface.
- Dark/light theme support if practical.
- Clear transfer direction.
- Progress bar.
- Activity log.
- Server management.

### Packaging

- Python source code.
- Requirements file.
- README documentation.
- PyInstaller build configuration.
- Windows executable build instructions.

---

# 4. Explicitly Out of Scope

The first version should **not** attempt to implement:

- Directory synchronization.
- Recursive folder transfer.
- FTP.
- FTPS.
- Rsync.
- Terminal/SSH shell functionality.
- Server administration.
- File editing.
- Multi-server parallel transfers.
- Password storage.
- Cloud credential storage.
- Automatic server discovery over the network.
- File compression/decompression.

If a folder needs to be transferred, the user can create a ZIP archive first.

---

# 5. Target Environment

## Host

- Windows 10/11.
- Python 3.x during development.
- Windows OpenSSH configuration located under the user's profile.

Typical SSH configuration:

```text
C:\Users\<username>\.ssh\config
```

Typical SSH known-hosts file:

```text
C:\Users\<username>\.ssh\known_hosts
```

## Remote Servers

- Linux servers.
- SSH server enabled.
- SCP/SFTP-compatible SSH access.
- Network connectivity from the Windows host.

---

# 6. Recommended Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3 |
| GUI | PySide6 |
| SSH | Paramiko |
| File Transfer | Paramiko/SCP implementation |
| Configuration | JSON |
| SSH Config Parsing | Paramiko |
| Packaging | PyInstaller |
| Testing | pytest |

The application should use a proper GUI framework rather than a basic command-line interface.

PySide6 is recommended because it provides a polished native desktop experience and good support for dialogs, tables, trees, progress bars, and background workers.

---

# 7. Core User Workflow

## 7.1 Upload Workflow

The user selects:

```text
Send to Server
```

Then:

1. Select a server.
2. Select a local file.
3. Specify or browse to the remote destination directory.
4. Click **Transfer**.
5. If password authentication is required, show a password prompt.
6. Connect to the server.
7. Transfer the file.
8. Display progress.
9. Display success/failure.
10. Close the connection.
11. Discard the password from application state.

Example:

```text
Windows

C:\Users\Alice\Documents\report.pdf
             |
             | SCP
             v
Linux

/home/alice/Documents/report.pdf
```

---

# 8. Upload Defaults

When **Send to Server** is selected:

### Local Source

No fixed default file.

The user selects a file through:

```text
[ Browse... ]
```

Example:

```text
C:\Users\Alice\Documents\report.pdf
```

### Remote Destination

Default to the remote user's home directory.

Instead of displaying only:

```text
~/
```

the GUI should display an explicit path such as:

```text
/home/alice/
```

This is intentional because the project requirement is to make paths unambiguous.

If the remote user's home directory cannot be determined before authentication, the application may initially construct the path from the configured username and/or resolve it after connecting.

---

# 9. Download Workflow

The user selects:

```text
Fetch from Server
```

Then:

1. Select a server.
2. Browse the remote filesystem.
3. Select a remote file.
4. Select or confirm the local destination.
5. Click **Transfer**.
6. Prompt for password if necessary.
7. Connect.
8. Transfer the file.
9. Display progress.
10. Display success/failure.
11. Close the connection.
12. Discard the password.

Example:

```text
Linux

/home/alice/Documents/report.pdf
             |
             | SCP
             v
Windows

C:\Users\Alice\Downloads\report.pdf
```

---

# 10. Download Defaults

When **Fetch from Server** is selected:

### Remote Source

The user selects the file using the remote browser.

Example:

```text
/home/alice/Documents/report.pdf
```

### Local Destination

Default:

```text
C:\Users\<WindowsUsername>\Downloads\
```

The user can change this with a folder picker.

---

# 11. Main GUI

The main window should have a simple transfer-focused design.

Suggested layout:

```text
┌──────────────────────────────────────────────────────────┐
│ SCP Transfer                                      ⚙      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Transfer                                                │
│                                                          │
│  [ ↑ Send to Server ]    [ ↓ Fetch from Server ]         │
│                                                          │
│  Server                                                  │
│  ┌───────────────────────────────────────────────┐       │
│  │ Production                                  ▼ │       │
│  └───────────────────────────────────────────────┘       │
│                                                          │
│  Source                                                  │
│  ┌──────────────────────────────────────────┐ [Browse]   │
│  │ C:\Users\Alice\Documents\report.pdf     │            │
│  └──────────────────────────────────────────┘            │
│                                                          │
│  Destination                                             │
│  ┌──────────────────────────────────────────┐ [Browse]   │
│  │ /home/alice/Documents/                  │            │
│  └──────────────────────────────────────────┘            │
│                                                          │
│              [         TRANSFER         ]                │
│                                                          │
│  Progress                                                │
│  ████████████████████░░░░░░░░  72%                      │
│                                                          │
│  72.4 MB / 100.2 MB     12.1 MB/s     ETA 00:02         │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Activity                                                 │
│                                                          │
│ 13:42:01  Connecting to Production...                   │
│ 13:42:02  Authentication successful                     │
│ 13:42:03  Transferring report.pdf                        │
│ 13:42:09  Transfer completed                            │
└──────────────────────────────────────────────────────────┘
```

---

# 12. Server Selection

The main window should provide a server dropdown.

Example:

```text
Server:
┌─────────────────────────────┐
│ Production              ▼  │
└─────────────────────────────┘
```

The dropdown can contain servers from:

- SSH config.
- Manually managed server configuration.

The application should make the source of a server clear if both sources are enabled.

Example:

```text
SSH Config
├── production
├── development
└── staging

Saved Servers
├── NAS
└── Backup Server
```

A grouped dropdown or server selector dialog is preferred over mixing everything without context.

---

# 13. SSH Config Support

The application should automatically inspect:

```text
%USERPROFILE%\.ssh\config
```

on startup or when the server list is refreshed.

Example SSH config:

```text
Host production
    HostName 192.168.1.100
    User alice
    Port 22

Host development
    HostName dev.example.com
    User bob
    Port 2222
```

The GUI should expose:

```text
production
development
```

as selectable servers.

The application should respect relevant SSH configuration settings supported by the implementation, including at minimum:

- Host
- HostName
- User
- Port

The architecture should allow additional SSH options to be supported later.

---

# 14. Manual Server Manager

A dedicated **Server Manager** should allow users to manage manually configured servers.

Features:

- Add server.
- Edit server.
- Delete server.
- Test connection.
- Enable/disable server.
- Select server.
- Validate required fields.

Suggested dialog:

```text
┌───────────────────────────────────────────────┐
│ Add Server                                    │
├───────────────────────────────────────────────┤
│                                               │
│ Name                                          │
│ [ Production                              ]   │
│                                               │
│ Hostname / IP                                 │
│ [ 192.168.1.100                           ]   │
│                                               │
│ Username                                      │
│ [ alice                                    ]   │
│                                               │
│ Port                                          │
│ [ 22                                       ]   │
│                                               │
│ Password                                      │
│ [ NOT STORED ]                                │
│                                               │
│          [Cancel]     [Test]     [Save]       │
└───────────────────────────────────────────────┘
```

There should be **no password input that gets saved with the server**.

The password should instead be requested when connecting.

---

# 15. Manual Server Configuration

Example internal configuration:

```json
{
    "servers": [
        {
            "name": "Production",
            "hostname": "192.168.1.100",
            "username": "alice",
            "port": 22
        },
        {
            "name": "Development",
            "hostname": "192.168.1.101",
            "username": "alice",
            "port": 22
        }
    ]
}
```

No password field should exist.

---

# 16. Password Authentication

Password authentication should work as follows:

```text
User selects server
        |
        v
Application attempts connection
        |
        v
Password required?
        |
       Yes
        |
        v
┌───────────────────────────────┐
│ Authentication Required       │
│                               │
│ Server: Production            │
│ User:   alice                 │
│                               │
│ Password:                     │
│ [••••••••••••••••••••]        │
│                               │
│              [Connect]        │
└───────────────────────────────┘
```

Security requirements:

- Do not save passwords to JSON.
- Do not save passwords to Windows registry.
- Do not write passwords to log files.
- Do not include passwords in exception messages.
- Do not display passwords in plain text.
- Keep the password only as long as needed.
- Clear references to the password when the connection finishes.
- Never include passwords in diagnostic output.

---

# 17. Remote File Browser

The remote browser should use a tree/list view.

Example:

```text
Remote: production
User: alice

Current path:
/home/alice/

┌──────────────────────────────────────┐
│ Name                  Type           │
├──────────────────────────────────────┤
│ ..                    Directory      │
│ Documents             Directory      │
│ Projects              Directory      │
│ Downloads             Directory      │
│ report.pdf            File           │
│ backup.zip            File           │
└──────────────────────────────────────┘

[ Up ] [ Refresh ] [ Select File ]
```

Requirements:

- List remote files and directories.
- Navigate into directories.
- Navigate to parent directory.
- Refresh.
- Show file names.
- Show file type.
- Optionally show file size and modified time.
- Select files only for transfer.
- Prevent directory selection in the first version.
- Clearly display the current remote path.

---

# 18. Remote Browser Safety

The remote browser should not allow accidental destructive operations.

The first version should be **read-only for the remote filesystem**.

It should not provide:

- Delete.
- Rename.
- Move.
- chmod.
- chown.
- Execute.
- Shell commands.

Its only purpose is to navigate and select files.

---

# 19. Local File Browser

For upload:

```text
[ Browse File... ]
```

For download:

```text
[ Browse Folder... ]
```

Windows-native dialogs should be used where practical.

---

# 20. File Name and Destination Handling

The application should handle:

- Spaces in file names.
- Unicode file names where supported.
- Existing destination files.
- Invalid paths.
- Missing directories.
- Read-only local destinations.
- Remote permission errors.

Before overwriting an existing local/remote file, the application should ask for confirmation.

Suggested dialog:

```text
File already exists.

C:\Users\Alice\Downloads\report.pdf

[Cancel] [Overwrite]
```

---

# 21. Transfer Progress

The transfer layer should provide enough information for the GUI to display:

- Bytes transferred.
- Total bytes.
- Percentage.
- Transfer speed.
- Estimated time remaining.
- Current file.
- Overall status.

Example:

```text
Transferring:

report.pdf

72.4 MB / 100.2 MB

████████████████████░░░░░░ 72%

Speed: 12.1 MB/s
ETA:   00:02
```

---

# 22. Background Transfers

The actual network transfer must not run on the GUI's main thread.

The application should use a worker/thread mechanism so that:

- The GUI remains responsive.
- Progress updates can be displayed.
- The user can cancel a transfer if supported.
- Exceptions can be safely returned to the GUI.

Recommended architecture:

```text
GUI Thread
    |
    | Start transfer
    v
Transfer Worker
    |
    +--> SSH Connection
    |
    +--> SCP Transfer
    |
    +--> Progress Events
    |
    v
GUI Updates
```

---

# 23. Transfer Cancellation

Preferred feature:

```text
[ Cancel Transfer ]
```

If cancellation is implemented:

- Stop the active transfer.
- Close the connection cleanly.
- Mark the transfer as cancelled.
- Avoid leaving misleading "completed" messages.
- Handle partially transferred files appropriately.

If safe cancellation is difficult for a specific transfer implementation, it can be deferred to a later version.

---

# 24. Activity Log

The application should have a visible activity log.

Example:

```text
13:42:01  Selected server: Production
13:42:01  Connecting to 192.168.1.100:22
13:42:02  Authentication successful
13:42:02  Starting upload
13:42:02  File: report.pdf
13:42:09  Transfer completed successfully
```

The log must never contain:

```text
Password: mySecretPassword
```

or any equivalent sensitive credential.

---

# 25. Error Handling

Errors should be converted into understandable messages.

Examples:

### Authentication failure

```text
Authentication failed.

The server rejected the supplied username/password.
```

### Connection failure

```text
Unable to connect to:

192.168.1.100:22

Check network connectivity and SSH availability.
```

### Missing remote file

```text
The selected remote file no longer exists.
```

### Permission denied

```text
Permission denied.

The current user does not have permission to access this file/path.
```

### Destination unavailable

```text
The selected destination directory does not exist or cannot be written to.
```

---

# 26. SSH Host Key Verification

The application should **not blindly disable host-key verification**.

Preferred behavior:

1. Use the user's known-hosts information where available.
2. Detect unknown hosts.
3. Warn the user.
4. Provide a controlled way to trust a new host key.
5. Reject changed host keys by default and clearly warn about the mismatch.

Example:

```text
Host Key Verification

The server's host key is not known.

Host:
192.168.1.100

Fingerprint:
SHA256:xxxxxxxxxxxxxxxx

Do you trust this host?

[Cancel] [Trust Once] [Trust]
```

The exact implementation should be designed carefully around Paramiko's host-key APIs.

---

# 27. Configuration Storage

The application should maintain a local configuration file for non-sensitive information.

Possible location:

```text
%APPDATA%\SCPTransferClient\
```

Example:

```text
%APPDATA%\SCPTransferClient\
├── config.json
└── servers.json
```

Stored information may include:

- Server names.
- Hostnames.
- Usernames.
- Ports.
- GUI preferences.
- Last selected server.
- Last used local directory.
- Last used remote directory.

Passwords must never be stored.

---

# 28. Application Architecture

Recommended structure:

```text
scp-client/
│
├── main.py
│
├── requirements.txt
├── README.md
├── LICENSE
│
├── app/
│   ├── __init__.py
│   │
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── server_manager.py
│   │   ├── password_dialog.py
│   │   ├── remote_browser.py
│   │   └── styles.py
│   │
│   ├── ssh/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── config_loader.py
│   │   └── host_keys.py
│   │
│   ├── transfer/
│   │   ├── __init__.py
│   │   ├── scp_client.py
│   │   ├── worker.py
│   │   └── progress.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── manager.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── paths.py
│       └── logging.py
│
├── tests/
│   ├── test_config.py
│   ├── test_ssh_config.py
│   ├── test_paths.py
│   └── test_transfer.py
│
├── assets/
│   └── icons/
│
└── build/
    └── scp-client.spec
```

---

# 29. Component Responsibilities

## `main.py`

Application entry point.

Responsibilities:

- Initialize Qt application.
- Load configuration.
- Initialize the main window.
- Start the application.

## `gui/main_window.py`

Main application interface.

Responsibilities:

- Transfer mode.
- Server selection.
- Source/destination fields.
- Transfer controls.
- Progress.
- Logs.

## `gui/server_manager.py`

Server management UI.

Responsibilities:

- Add.
- Edit.
- Delete.
- Test.
- List servers.

## `gui/password_dialog.py`

Secure password prompt.

Responsibilities:

- Request password.
- Mask password.
- Return password to connection layer.
- Never persist password.

## `gui/remote_browser.py`

Remote filesystem navigation.

Responsibilities:

- Browse directories.
- Display files.
- Select files.
- Return selected remote path.

## `ssh/config_loader.py`

SSH configuration handling.

Responsibilities:

- Locate Windows SSH config.
- Parse SSH config.
- Extract usable host definitions.
- Return normalized server information.

## `ssh/connection.py`

SSH connection management.

Responsibilities:

- Establish SSH connection.
- Authenticate.
- Load host keys.
- Close connections.
- Expose SFTP/SCP operations.

## `transfer/scp_client.py`

File transfer abstraction.

Responsibilities:

- Upload.
- Download.
- Progress callbacks.
- File validation.

## `transfer/worker.py`

Background transfer worker.

Responsibilities:

- Run transfers outside GUI thread.
- Emit progress.
- Emit success.
- Emit failure.
- Handle cancellation.

## `config/manager.py`

Configuration persistence.

Responsibilities:

- Load JSON.
- Save JSON.
- Validate configuration.
- Never store credentials.

---

# 30. Server Data Model

A server should conceptually contain:

```text
Server
├── name
├── hostname
├── username
├── port
└── source
```

Example:

```python
Server(
    name="Production",
    hostname="192.168.1.100",
    username="alice",
    port=22,
    source="manual"
)
```

SSH-config servers should have:

```text
source="ssh_config"
```

This allows the GUI to distinguish between server sources.

---

# 31. Transfer Data Model

A transfer request should contain:

```text
TransferRequest
├── direction
├── server
├── source_path
├── destination_path
└── overwrite
```

Direction:

```text
UPLOAD
DOWNLOAD
```

Example upload:

```text
direction: UPLOAD
server: Production
source_path: C:\Users\Alice\Documents\report.pdf
destination_path: /home/alice/Documents/
```

Example download:

```text
direction: DOWNLOAD
server: Production
source_path: /home/alice/Documents/report.pdf
destination_path: C:\Users\Alice\Downloads\
```

---

# 32. Security Requirements

Security is a core requirement.

## Never Store

- SSH passwords.
- Passwords in JSON.
- Passwords in logs.
- Passwords in source code.
- Passwords in environment-independent application configuration.
- Passwords in crash reports.

## Avoid

- Disabling host-key verification globally.
- Logging complete connection credentials.
- Passing passwords through command-line arguments.
- Embedding credentials in SCP command strings.

## Use

- Encrypted SSH transport.
- Proper host-key verification.
- Masked password input.
- In-memory credentials only.
- Clean connection shutdown.

---

# 33. Logging Requirements

Logs should be useful for troubleshooting without exposing secrets.

Safe:

```text
Connecting to server: production
Username: alice
Host: 192.168.1.100
Port: 22
Authentication successful
```

Unsafe:

```text
Password: hunter2
```

The logging layer should also avoid dumping complete exception objects if they might contain sensitive connection information.

---

# 34. UX Requirements

The application should prioritize simplicity.

A normal transfer should require approximately:

```text
Select direction
      ↓
Select server
      ↓
Select file
      ↓
Confirm destination
      ↓
Transfer
```

The user should not need to understand SCP command syntax.

---

# 35. Default Paths

## Upload

Remote destination:

```text
/home/<remote_username>/
```

Example:

```text
/home/alice/
```

## Download

Local destination:

```text
C:\Users\<WindowsUsername>\Downloads\
```

Example:

```text
C:\Users\Alice\Downloads\
```

The application should detect the actual Windows user and avoid hardcoding `Alice`.

---

# 36. Path Rules

The application must treat Windows and Linux paths separately.

Windows:

```text
C:\Users\Alice\Documents\report.pdf
```

Linux:

```text
/home/alice/Documents/report.pdf
```

The application must not attempt to use Windows path manipulation logic for remote Linux paths.

Remote paths should use POSIX-style handling.

Local paths should use Windows-native path handling.

---

# 37. Validation

Before starting a transfer:

## Upload

Validate:

- Server selected.
- Local file exists.
- Local path is a file.
- Remote destination is not empty.
- User is authenticated.

## Download

Validate:

- Server selected.
- Remote file selected.
- Local destination exists or can be created.
- Local destination is writable.

---

# 38. Overwrite Behavior

Default behavior:

**Ask before overwriting.**

Example:

```text
The destination file already exists.

C:\Users\Alice\Downloads\report.pdf

Do you want to replace it?

[Cancel] [Overwrite]
```

This prevents accidental data loss.

---

# 39. Testing Requirements

The project should include automated tests where practical.

Test areas:

### Configuration

- Load valid JSON.
- Reject invalid JSON.
- Add server.
- Edit server.
- Delete server.
- Ensure password is never serialized.

### SSH Config

- Parse normal SSH config.
- Parse multiple hosts.
- Extract username.
- Extract hostname.
- Extract port.
- Handle missing config file.

### Paths

- Validate Windows paths.
- Validate remote POSIX paths.
- Determine Downloads directory.
- Determine Windows username.

### Transfer

Use mocks/fakes for network operations where possible.

Test:

- Upload request.
- Download request.
- Progress reporting.
- Authentication failure.
- Connection failure.
- Missing file.
- Permission failure.

---

# 40. Dependency Requirements

Initial dependency set should be kept small.

Example:

```text
PySide6
paramiko
scp
```

Development/test dependencies:

```text
pytest
```

Potential `requirements.txt`:

```text
PySide6
paramiko
scp
```

Potential development requirements:

```text
pytest
pyinstaller
```

Exact versions should be pinned after testing the application.

---

# 41. Packaging

The final project should support building a Windows executable with PyInstaller.

Target:

```text
SCPTransferClient.exe
```

Prefer a GUI application without a console window.

Example build concept:

```text
pyinstaller --windowed --name SCPTransferClient main.py
```

The final project should include a `.spec` file if additional assets/resources are required.

---

# 42. README Requirements

The project README should document:

1. What the application does.
2. Supported operating systems.
3. Python version.
4. Installation.
5. Dependency installation.
6. Running from source.
7. SSH config usage.
8. Manual server configuration.
9. Password behavior.
10. Upload workflow.
11. Download workflow.
12. Remote browser.
13. Host-key verification.
14. Troubleshooting.
15. Building the Windows executable.
16. Security notes.

---

# 43. Future Features

These are intentionally not part of version 1 but the architecture should not prevent them.

Possible future additions:

- Drag-and-drop files.
- Multiple file queue.
- Transfer history.
- Resume interrupted transfers.
- Saved transfer presets.
- System tray support.
- Notifications.
- SSH key authentication.
- SFTP mode.
- Folder transfers.
- Remote file search.
- Bookmarked remote directories.
- Speed limiting.
- Multiple simultaneous transfers.
- Connection profiles.
- Custom themes.

---

# 44. Version 1 Acceptance Criteria

Version 1 is considered complete when the following work:

### Server Management

- [ ] SSH config is automatically detected.
- [ ] SSH-config servers appear in the application.
- [ ] Manual servers can be added.
- [ ] Manual servers can be edited.
- [ ] Manual servers can be deleted.
- [ ] Manual server passwords are never stored.

### Upload

- [ ] User can select a server.
- [ ] User can select a local file.
- [ ] Remote username is clearly displayed.
- [ ] Remote home directory is used as the default.
- [ ] User can change the remote destination.
- [ ] Password prompt works.
- [ ] File transfers successfully.
- [ ] Progress is displayed.
- [ ] Errors are handled.

### Download

- [ ] User can select a server.
- [ ] User can browse the remote filesystem.
- [ ] User can select a remote file.
- [ ] Downloads defaults to the Windows Downloads directory.
- [ ] User can change the local destination.
- [ ] Password prompt works.
- [ ] File transfers successfully.
- [ ] Progress is displayed.
- [ ] Errors are handled.

### Security

- [ ] Passwords are never persisted.
- [ ] Passwords are never logged.
- [ ] SSH traffic is encrypted.
- [ ] Host-key verification is handled safely.
- [ ] Unknown/changed host keys generate appropriate warnings.

### GUI

- [ ] Application does not freeze during transfers.
- [ ] Transfer direction is obvious.
- [ ] Source and destination paths are clearly labeled.
- [ ] Activity log is available.
- [ ] Success/failure status is clearly displayed.

### Packaging

- [ ] Application can be built as a Windows executable.
- [ ] Executable launches without a console window.
- [ ] README explains installation and usage.

---

# 45. Suggested Development Phases

## Phase 1 — Project Foundation

- Set up Python project.
- Set up PySide6.
- Create main window.
- Establish project architecture.
- Create configuration models.

## Phase 2 — Server Management

- Implement manual server storage.
- Implement Server Manager GUI.
- Add/edit/delete servers.
- Add validation.

## Phase 3 — SSH Config

- Locate Windows SSH config.
- Parse configured hosts.
- Populate server selector.
- Normalize server configuration.

## Phase 4 — SSH Authentication

- Implement Paramiko connection.
- Implement password prompt.
- Implement host-key handling.
- Implement clean connection lifecycle.

## Phase 5 — Remote Browser

- Implement remote directory listing.
- Implement navigation.
- Implement file selection.
- Display explicit remote paths.

## Phase 6 — SCP Transfer

- Implement upload.
- Implement download.
- Add progress callbacks.
- Add background worker.
- Add error handling.

## Phase 7 — GUI Integration

- Connect all components.
- Implement transfer workflow.
- Add status/logging.
- Add overwrite confirmation.
- Add cancellation if supported.

## Phase 8 — Testing

- Unit tests.
- Integration testing against Linux SSH server.
- Authentication testing.
- Large-file testing.
- Failure/reconnection testing.

## Phase 9 — Packaging

- PyInstaller configuration.
- Windows executable.
- Test on clean Windows installation.
- Final documentation.

---

# 46. Final Product Concept

The finished application should feel like a small, focused alternative to a full SCP client:

```text
                 SCP TRANSFER CLIENT
                         │
          ┌──────────────┴──────────────┐
          │                             │
     SEND TO SERVER              FETCH FROM SERVER
          │                             │
          ▼                             ▼
    Select Server                 Select Server
          │                             │
          ▼                             ▼
    Select Local File            Browse Remote Files
          │                             │
          ▼                             ▼
    Remote Destination            Select Remote File
          │                             │
          └──────────────┬──────────────┘
                         ▼
                  Password Prompt
                         │
                         ▼
                   SSH Connection
                         │
                         ▼
                    SCP Transfer
                         │
                         ▼
                Progress + Logging
                         │
                         ▼
                    Completed
```

The guiding principle should be:

> **Make SCP transfers as simple as selecting a server, selecting a file, and pressing Transfer — while keeping credentials secure and paths unambiguous.**

---

# 47. Deliverables

The completed project should provide:

- [ ] Complete Python source code.
- [ ] Modern PySide6 GUI.
- [ ] Upload functionality.
- [ ] Download functionality.
- [ ] SSH config integration.
- [ ] Manual server manager.
- [ ] Password prompt.
- [ ] No password persistence.
- [ ] Remote filesystem browser.
- [ ] Local Windows file/folder browser.
- [ ] Explicit Windows/Linux paths.
- [ ] Progress bar.
- [ ] Transfer speed/ETA.
- [ ] Activity log.
- [ ] Error handling.
- [ ] Host-key verification.
- [ ] Overwrite confirmation.
- [ ] Background transfer worker.
- [ ] Automated tests.
- [ ] `requirements.txt`.
- [ ] PyInstaller configuration.
- [ ] Windows executable build instructions.
- [ ] Comprehensive README.
- [ ] Security documentation.

---

# 48. Definition of Done

The project is ready for normal use when a Windows user can launch the application, select either **Send to Server** or **Fetch from Server**, choose a server from SSH config or manually configured servers, select the required file using the GUI, authenticate with a prompted password, complete the transfer, and verify the result — without the application ever storing the password.
