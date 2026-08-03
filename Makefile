.PHONY: help run check clean install-autostart uninstall-autostart

PYTHON ?= python3
MAIN := src/main.py
AUTOSTART_DIR := $(HOME)/.config/autostart
AUTOSTART_FILE := $(AUTOSTART_DIR)/gmail-notification.desktop
DESKTOP_TEMPLATE := assets/gmail-notification.desktop.in

help:
	@echo "Gmail Notification"
	@echo ""
	@echo "Targets:"
	@echo "  make run                    Run the tray indicator"
	@echo "  make install-autostart      Start app in background on login"
	@echo "  make uninstall-autostart    Remove login autostart entry"
	@echo "  make check                  Verify Python/GObject dependencies"
	@echo "  make clean                  Remove Python cache files"

run:
	$(PYTHON) $(MAIN)

install-autostart:
	@mkdir -p $(AUTOSTART_DIR)
	@sed -e 's|@PROJECT_ROOT@|$(CURDIR)|g' \
		-e 's|@PYTHON@|$(shell command -v $(PYTHON))|g' \
		$(DESKTOP_TEMPLATE) > $(AUTOSTART_FILE)
	@echo "Installed $(AUTOSTART_FILE)"
	@echo "The app will start in the background on next login."

uninstall-autostart:
	@rm -f $(AUTOSTART_FILE)
	@echo "Removed $(AUTOSTART_FILE)"

check:
	@$(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import Gtk" \
		2>/dev/null || $(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AppIndicator3', '0.1'); from gi.repository import Gtk"
	@echo Dependencies OK

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
