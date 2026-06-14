PLUGIN_NAME := BatteryCalibrator
PLUGIN_DIR := /home/deck/homebrew/plugins/$(PLUGIN_NAME)
SRC_DIR := $(CURDIR)
PW := echo "Decky!" | sudo -S

.PHONY: all build dev-deploy clean lint typecheck

all: build

build:
	pnpm run build
	ruff check py_modules/battery_calibrator/ main.py

lint:
	ruff check py_modules/battery_calibrator/ main.py

typecheck:
	pyright py_modules/battery_calibrator/ main.py

dev-deploy: build
	@echo "==> Deploying $(PLUGIN_NAME) to $(PLUGIN_DIR)"
	$(PW) mkdir -p $(PLUGIN_DIR)
	$(PW) ln -sf $(SRC_DIR)/dist $(PLUGIN_DIR)/dist
	$(PW) ln -sf $(SRC_DIR)/py_modules $(PLUGIN_DIR)/py_modules
	$(PW) ln -sf $(SRC_DIR)/main.py $(PLUGIN_DIR)/main.py
	$(PW) ln -sf $(SRC_DIR)/package.json $(PLUGIN_DIR)/package.json
	$(PW) ln -sf $(SRC_DIR)/plugin.json $(PLUGIN_DIR)/plugin.json
	@echo "==> Done. 'pnpm run build' auto-updates the plugin. Restart Steam to reload."

clean:
	rm -rf dist/
	pnpm install
