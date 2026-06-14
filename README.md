# Battery Calibrator

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for the Steam Deck that provides intelligent battery charge management, automated calibration cycles, and health monitoring — inspired by AlDente for macOS.

## ✨ At a Glance

| Feature | Benefit |
|---------|---------|
| **Charge Limit Control** | Limit charge to 20–100% to preserve battery lifespan |
| **Smart Auto-Cycling** | Auto-pause/resume charging within a configurable range (e.g. 30–80%) |
| **Heat Protection** | Pause charging when battery exceeds 40°C; resume at 38°C |
| **Calibration Engine** | Guided discharge→recharge cycles to keep fuel gauge accurate |
| **Charge Rate Limiting** | Cap charging current (0.5–3A) to reduce heat during gaming |
| **Sailing Mode** | Long-term storage preset: 70% limit, scheduler disabled |
| **Quick Presets** | One-tap access to Storage (60%), Normal (80%), Travel (95%), Full (100%) |
| **Full Profiles** | Save/load complete configurations |
| **Health History** | Visual graph of battery health % over time |
| **QAM Widget** | Compact battery status in Decky quick access menu |
| **Zero Polling** | Event-driven via udevadm; no CPU cost during gameplay |
| **No Root Required** | Uses D-Bus; sysfs fallback automatic |

## Features

### Charge Management
- **Charge Limit Control** — Set maximum charge level (20–100%) via D-Bus or sysfs to prolong battery lifespan.
- **Smart Charge Thresholds** — Auto-cycle between a min and max range (e.g. 30–80%). When capacity drops to the min, charging resumes. When it hits the max, it stops. Keeps the battery in the ideal band through normal use.
- **Extended Range** — Enable 20–100% range (default 50–100%) for deeper discharge control.
- **Charge Rate Control** — Limit charging current (0.5A–3A) to reduce heat during gaming.
- **Pause / Top-Up** — Pause charging at the current level, or temporarily charge to 100% and automatically restore the limit.
- **Quiet Mode** — Caps charge rate to 0.5A always; shows real-time power draw (battery W + charger input W).

### Battery Health
- **Automated Calibration** — Guided discharge→recharge cycle to maintain accurate fuel gauge readings. Configurable interval (7 / 14 / 21 / 30 days) and drain threshold.
- **Heat Protection** — When battery temp exceeds 40°C, charging pauses until it cools to 38°C. 5-minute cooldown after resume prevents rapid re-triggering.
- **Sailing Mode** — Long-term storage preset: limit to 70%, scheduler disabled.
- **Battery Health Display** — Real-time capacity, health %, cycle count, power, voltage, current, and temperature.
- **Crash Recovery** — If the plugin crashes during calibration, it auto-restores the correct limit on restart.

### Presets & Profiles
- **Charge Presets** — Quick-apply presets (Storage 60%, Normal 80%, Full 100%, Travel 95%).
- **Full Profiles** — Save and load complete configurations (charge limit, smart charge settings, heat protection, charge rate, calibration interval).

### Monitoring & UI
- **Health History Graph** — SVG line chart of health % over time with trend analysis.
- **Calibration Log** — Table of past calibrations with results and timestamps.
- **Quick Access Widget** — Compact battery card in the Decky QAM (`...` menu) with live data and Pause button.
- **Info Tips** — `ⓘ` buttons next to every feature explaining what it does.
- **Zero Polling** — Uses `udevadm monitor` for battery events. On udevadm failure, falls back to sysfs polling (5s interval). No CPU impact during gameplay.
- **PD Power Data** — Shows USB Power Delivery contract: voltage (V), current (mA), and power (W).

### Behind the Scenes
- **No Root Required** — Primary interface uses D-Bus (`SetMaxChargeLevel`); falls back to sysfs automatically.
- **SQLite History** — Persistent snapshot and calibration logs for 90-day retention and trend tracking.
- **Notifications** — Toasts for calibration due, complete, timed-out, and top-up done.
- **Async Architecture** — Pure asyncio; no blocking operations. Graceful cleanup on shutdown.

## Installation

### From Decky Store (Recommended)
1. Open Decky Loader in Gaming Mode.
2. Navigate to the shop and search for "Battery Calibrator".
3. Click install.
4. Press `...` (QAM) → Battery Calibrator to open the plugin.

### Manual Installation
1. [Download the latest release](https://github.com/anomalyco/decky-battery-calibrator/releases).
2. Extract the zip to `/home/deck/homebrew/plugins/`.
3. Restart Steam or reload Decky (Settings → Decky → Reload).

## Quick Start

1. **Open the plugin** — Press `...` in Gaming Mode → Battery Calibrator.
2. **Set a charge limit** — Drag the slider to your desired max (e.g., 80% for normal use).
3. **Optional: Enable heat protection** — Toggle "Heat Protection" if you game in a hot environment.
4. **Optional: Schedule calibration** — Set interval (14 days default) and drain threshold (5% default).
5. **Monitor** — Watch the health graph and battery card in QAM.

### Common Scenarios

| Scenario | Setup |
|----------|-------|
| **Daily gaming** | Set limit to 80%, enable heat protection |
| **Long storage** | Toggle "Sailing Mode" (70% limit, scheduler off) |
| **Optimal aging** | Set limit to 60%, calibrate every 2 weeks |
| **Road trip** | Load "Travel" preset (95% limit, higher rate) |
| **Quiet mode** | Toggle "Quiet Mode" to cap at 0.5A; watch power draw |

## Troubleshooting

### "Battery data not updating"
- **Cause**: udevadm monitor failed to start; fallback to sysfs polling (5s interval) is active.
- **Action**: None required; polling works fine. Check logs: `journalctl -u decky-loader | grep "falling back"`
- **If stuck**: Restart Decky Loader: `sudo systemctl restart decky-loader`

### "Calibration not starting / stuck"
- **Cause**: Charger not plugged in, or calibration already in progress.
- **Action**: Plug in charger, wait for battery to stabilize (10s), try again.
- **If stuck**: Check calibration log for last result; if timed-out, try resetting via profile load.

### "Charge limit not applying"
- **Cause**: D-Bus unavailable; sysfs write failed or not found.
- **Action**: Plugin logs fallback attempt. Check: `cat /sys/class/power_supply/BAT1/max_battery_charge_level`
- **If missing**: Your kernel may not support charge limits. Check Decky forum.

### "Heat protection pausing constantly"
- **Cause**: Ambient temperature high or battery thermal sensor off-calibration.
- **Action**: Ensure good ventilation, close games, check logs: `journalctl -u decky-loader | grep "Heat protection"`

### "Plugin crashes on startup"
- **Cause**: Corrupted settings or history database.
- **Action**: Reset settings: `rm -rf ~/.config/decky-battery-calibrator/` then restart Decky Loader.

## Development

### Prerequisites
- Node.js v22.14+
- pnpm 11.x
- Python 3.13+
- uv (Python package manager)
- Decky Loader (for testing on-device)

### Setup
```bash
git clone https://github.com/anomalyco/decky-battery-calibrator.git
cd decky-battery-calibrator
pnpm install
pnpm run build
```

### Project Structure
```
decky-battery-calibrator/
├── main.py                          # Plugin entry point (Decky Python backend)
├── py_modules/battery_calibrator/   # Python package
│   ├── battery.py                   # Sysfs battery reader (capacity, temp, health, etc.)
│   ├── calibration.py               # Calibration state machine
│   ├── charge_control.py            # D-Bus / sysfs charge limit
│   ├── history.py                   # SQLite history database
│   ├── presets.py                   # Charge limit presets
│   ├── rate_control.py              # Charge rate limiter
│   ├── scheduler.py                 # Calibration scheduler
│   ├── settings.py                  # JSON settings persistence
│   ├── thermal.py                   # Heat protection (pauses charging when hot)
│   ├── _constants.py                # Constants and enums
│   └── _exceptions.py               # Custom exceptions
├── src/index.tsx                    # React frontend (app + QAM widget)
├── tests/                           # Pytest test suite (167 tests)
├── Makefile                         # Build & deploy automation
├── plugin.json                      # Decky plugin metadata
├── package.json                     # Node/pnpm dependencies
├── README.md                        # This file
└── LICENSE                          # BSD 3-Clause
```

### Commands
| Command | Description |
|---|---|
| `pnpm run build` | Build TypeScript frontend |
| `pnpm run watch` | Watch mode for development |
| `make dev-deploy` | Build + deploy to Decky plugins directory |
| `pytest tests/` | Run backend test suite (167 tests) |
| `ruff check py_modules/ tests/ main.py` | Lint Python code |
| `pyright py_modules/ main.py` | Type-check Python code |

### Architecture
- **Zero polling** — Battery events flow through `udevadm monitor` → `main.py` → `calibration.py` (state machine), `thermal.py` (heat check), `_apply_smart_charge()` (range cycling). On udevadm failure, falls back to sysfs polling every 5s. The frontend receives events only on state changes via Decky's event system.
- **Safe defaults** — Every module degrades gracefully. If D-Bus is unavailable, sysfs is used. If sysfs is missing, operations are no-ops. Invalid settings fall back to defaults.
- **Event-driven** — No `setInterval` anywhere. The scheduler calculates seconds-to-next-due and sleeps once. Battery monitoring is driven by kernel udev events or fallback sysfs polling.
- **QAM Widget** — Registered via `routerHook.addGlobalComponent()`, renders only when the quick access menu is visible, updates via event listeners.
- **Null Safety** — Frontend uses optional chaining (`?.`) and nullish coalescing (`??`) to safely handle undefined/null from backend.

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=py_modules/battery_calibrator --cov-report=term-missing

# Run specific test file
pytest tests/test_calibration.py -v

# All 167 tests pass across 10 test files:
# test_battery, test_calibration, test_charge_control,
# test_history, test_main, test_presets, test_rate_control,
# test_scheduler, test_settings, test_thermal
```

## License

BSD 3-Clause. See [LICENSE](LICENSE).

## Acknowledgments
- [Steam Deck Homebrew](https://github.com/SteamDeckHomebrew) for Decky Loader
- [AlDente](https://apphousekitchen.com/) for the charge-limiting inspiration
- [Linux kernel](https://kernel.org/) for hwmon and power_supply APIs

