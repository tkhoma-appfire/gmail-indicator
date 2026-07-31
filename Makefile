.PHONY: help run check clean

PYTHON ?= python3
MAIN := src/main.py

help:
	@echo "Gmail Notification"
	@echo ""
	@echo "Targets:"
	@echo "  make run                    Run the tray indicator"
	@echo "  make check                  Verify Python/GObject dependencies"
	@echo "  make clean                  Remove Python cache files"

run:
	$(PYTHON) $(MAIN)

check:
	@$(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import Gtk" \
		2>/dev/null || $(PYTHON) -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AppIndicator3', '0.1'); from gi.repository import Gtk"
	@echo Dependencies OK

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
