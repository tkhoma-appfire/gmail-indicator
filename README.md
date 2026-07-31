# Gmail Notification

A Python application that runs in the Ubuntu top bar using [AppIndicator](https://github.com/AyatanaIndicators/libayatana-appindicator). It shows a tray icon with a context menu and stays running in the background.

## Requirements

- Ubuntu (or another Linux desktop with AppIndicator support)
- Python 3.10+
- GTK 3 and Ayatana AppIndicator GObject bindings

## Installation

Install system dependencies:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

On GNOME, tray icons are disabled by default. Enable the AppIndicator extension:

```bash
sudo apt install gnome-shell-extension-appindicator
gnome-extensions enable appindicatorsupport@ubuntu.com
```

Log out and back in after enabling the extension.

## Usage

Run the application:

```bash
make run
```

Or:

```bash
python3 src/main.py
```

An envelope icon appears in the top bar. Right-click it to open the menu.

Quit with **Quit** from the menu or `Ctrl+C` in the terminal.

## Project structure

```
gmail-notification/
├── src/
│   ├── main.py       # AppIndicator entry point
│   ├── popup.py      # Top-bar popup window
│   └── tray_menu.py  # Right-click tray menu
├── assets/
│   └── icon.svg      # Tray icon
└── requirements.txt  # System package notes
```

## Troubleshooting

**Icon does not appear**

- Confirm the AppIndicator GNOME extension is installed and enabled.
- Log out and back in after enabling the extension.
- Make sure the app is still running (`make run`).

**`Namespace AppIndicator3 not available`**

- Install `gir1.2-ayatanaappindicator3-0.1`. On Ubuntu 24.04 the library is exposed as `AyatanaAppIndicator3`; the app handles both old and new names automatically.

## License

MIT
