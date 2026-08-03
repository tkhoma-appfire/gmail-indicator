# Gmail Notification

A Python application that runs in the Ubuntu top bar using [AppIndicator](https://github.com/AyatanaIndicators/libayatana-appindicator). It shows a tray icon with a right-click context menu and a popup that lists upcoming events from your Google Calendar.

## Features

- Tray icon in the Ubuntu top bar
- Context menu on right-click only
- Popup below the tray icon showing upcoming calendar events (next 7 days)
- Google Calendar OAuth2 authentication with token caching

## Requirements

- Ubuntu (or another Linux desktop with AppIndicator support)
- Python 3.10+
- GTK 3 and Ayatana AppIndicator GObject bindings
- Google Calendar API Python libraries
- A Google Cloud project with the Calendar API enabled

## Installation

Install system dependencies:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

Install Python dependencies (Ubuntu packages):

```bash
sudo apt install python3-googleapi python3-google-auth-oauthlib
```

Alternatively, with pip:

```bash
sudo apt install python3-pip
pip install -r requirements.txt
```

On GNOME, tray icons are disabled by default. Enable the AppIndicator extension:

```bash
sudo apt install gnome-shell-extension-appindicator
gnome-extensions enable appindicatorsupport@ubuntu.com
```

Log out and back in after enabling the extension.

## Google Calendar setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Calendar API** for that project.
3. Go to **APIs & Services → Credentials** and create an **OAuth 2.0 Client ID** (Desktop app).
4. Download the credentials file and save it as `credentials.json` in the project root.
5. Run the app and choose **Show popup** from the tray menu. A browser window opens for Google sign-in on first use.
6. After sign-in, `token.json` is saved locally and reused on later runs.

Do not commit `credentials.json` or `token.json` (they are listed in `.gitignore`).

## Usage

Run the application:

```bash
make run
```

Or:

```bash
python3 src/main.py
```

An envelope icon appears in the top bar.

- **Right-click** the icon to open the menu.
- Choose **Show popup** to open a dropdown with your upcoming calendar events.
- Click outside the popup or press `Escape` to close it.
- Choose **Quit** from the menu or press `Ctrl+C` in the terminal to exit.

## Run on startup

Install a login autostart entry so the app runs in the background when you sign in:

```bash
make install-autostart
```

This creates `~/.config/autostart/gmail-notification.desktop`. Log out and back in (or reboot) for it to take effect.

To remove it:

```bash
make uninstall-autostart
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make run` | Start the tray indicator |
| `make install-autostart` | Start app in background on login |
| `make uninstall-autostart` | Remove login autostart entry |
| `make check` | Verify Python/GObject dependencies |
| `make clean` | Remove Python cache files |

## Project structure

```
gmail-notification/
├── src/
│   ├── main.py              # AppIndicator entry point
│   ├── popup.py             # Top-bar popup window
│   ├── tray_menu.py         # Right-click tray menu
│   └── google_calendar.py   # Google Calendar API client
├── assets/
│   ├── icon.svg             # Tray icon
│   └── gmail-notification.desktop.in  # Autostart template
├── credentials.json         # Google OAuth credentials (not in git)
├── token.json               # Saved auth token (not in git)
├── Makefile
└── requirements.txt
```

## Troubleshooting

**Icon does not appear**

- Confirm the AppIndicator GNOME extension is installed and enabled.
- Log out and back in after enabling the extension.
- Make sure the app is still running (`make run`).

**`Namespace AppIndicator3 not available`**

- Install `gir1.2-ayatanaappindicator3-0.1`. On Ubuntu 24.04 the library is exposed as `AyatanaAppIndicator3`; the app handles both old and new names automatically.

**`No module named 'googleapiclient'` or `No module named 'google_auth_oauthlib'`**

- Install the Google API packages: `sudo apt install python3-googleapi python3-google-auth-oauthlib`
- Or use pip: `pip install -r requirements.txt`

**Popup shows "Missing credentials.json"**

- Follow the [Google Calendar setup](#google-calendar-setup) steps and place `credentials.json` in the project root.

**Popup shows a calendar API or auth error**

- Confirm the Google Calendar API is enabled in your Cloud project.
- Delete `token.json` and sign in again if the saved token is invalid or expired.

## License

MIT
