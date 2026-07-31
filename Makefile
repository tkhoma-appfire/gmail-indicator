.PHONY: help run install-deps install-gnome-extension check clean

PYTHON ?= python3
MAIN := src/main.py

APT_PACKAGES := python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
GNOME_PACKAGES := gnome-shell-extension-appindicator

help:
	@echo "Gmail Notification"
	@echo ""
	@echo "Targets:"
	@echo "  make run                    Run the tray indicator"
	@echo "  make install-deps           Install required apt packages"
	@echo "  make install-gnome-extension Install and enable GNOME tray extension"
	@echo "  make check                  Verify Python/GObject dependencies"
	@echo "  make clean                  Remove Python cache files"

run:
	$(PYTHON) $(MAIN)

install-deps:
	sudo apt install -y $(APT_PACKAGES)

install-gnome-extension:
	sudo apt install -y $(GNOME_PACKAGES)
	gnome-extensions enable appindicatorsupport@ubuntu.com
	@echo "Log out and back in for the extension to take effect."

check:
	@$(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import Gtk" \
		2>/dev/null || $(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AppIndicator3', '0.1'); from gi.repository import Gtk"
	@echo Dependencies OK

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
