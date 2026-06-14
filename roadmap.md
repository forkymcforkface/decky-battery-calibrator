# Battery Calibrator — Roadmap

Feature inventory surveyed from: **AlDente Pro**, **Battery Toolkit** (macOS), **TLP** (Linux),
**PowerTop**, **AccuBattery** (Android), **BatteryBar** (Windows), **GNOME Power Profiles**.

---

## Phase 1 — Core (MVP)
- [x] Project scaffold (Decky plugin template)
- [x] Read battery status (capacity, status, health, cycles, power)
- [x] Set charge limit via SteamosManager D-Bus
- [x] Set charge limit via sysfs fallback
- [x] Charge limit slider in UI (50–100%)
- [x] Battery temperature display (sysfs `temp`, converted from 0.1°C)
- [x] Battery dashboard (voltage, current, power, health %, cycle count)

## Phase 2 — Calibration
- [x] Calibration state machine: IDLE → UNPLUG_AND_DRAIN → PLUG_IN_AND_CHARGE → COMPLETE / TIMED_OUT
- [x] Manual "start calibration" button → sets 100%, emits notifications
- [x] Auto-detect drain (battery < threshold while unplugged)
- [x] Auto-detect recharge (hits 100% while plugged in) → restore limit
- [x] Timeout fallback (48h → restore limit)
- [x] Calibration progress display in UI (phase, last result, timed-out indicator)
- [x] Calibration log table in UI

## Phase 3 — Scheduler
- [x] Configurable interval (7 / 14 / 21 / 30 days)
- [x] Next-run date shown in UI
- [x] Auto-trigger calibration on schedule
- [x] One-shot async sleep (no polling loop)

## Phase 4 — Advanced Charge Control
- [x] Expand limit range to 20–100% (with toggle for extended range)
- [x] Quick presets: "Storage" (60%), "Normal" (80%), "Full" (100%), "Travel" (95%)
- [x] Custom named presets (`PresetManager`)
- [x] Charge rate limiting (write `max_battery_charge_rate` sysfs, 0.5A–3A)
- [x] "Pause charging" button → set limit to current %
- [x] Top Up — charge to 100% once, then return to normal limit
- [x] InfoTip `ⓘ` buttons explaining each feature

## Phase 5 — Monitoring & History
- [x] Real-time dashboard (%, status, power, voltage, current, temp)
- [x] Health history graph (SVG line chart, health % over time)
- [x] Cycle count tracking
- [x] Session logging (charge/discharge/snapshot history via SQLite)
- [ ] Export history (CSV/JSON) — low priority

## Phase 6 — Smart Protection
- [x] Heat protection — **pause charging** if battery temp > 45°C, resume when < 43°C (hysteresis)
- [x] "Sailing Mode" — limit to 70%, scheduler disabled, for long-term storage
- [x] Smart charge thresholds — auto-cycle between configurable min/max (e.g. 30–80%) on battery events
- [x] Charge complete notification (top-up auto-restore)
- [x] Calibration due notification

## Phase 7 — Extended Features
- [x] Full profiles — save/load/delete complete setting snapshots
- [x] QAM widget — compact battery card with Pause button in quick access menu
- [x] InfoTip buttons — clickable `ⓘ` icons with Decky toast explanations for every feature
- [x] Event-driven design — no `setInterval`, no polling, pure udev events + async scheduler
- [x] 161 tests, 0 lint errors, 0 type errors

## Phase 8 — Polish & Distribution
- [ ] Decky store submission (PR to decky-plugin-database)
- [ ] GitHub release page with pre-built zips
- [ ] Screenshots and demo GIF in README
- [ ] Icons and proper plugin.json metadata

---

## Won't Do (hardware-impossible on Steam Deck)

| Feature | Why |
|---------|------|
| **True discharge while plugged** | EC/firmware doesn't support bypassing charger |
| **MagSafe LED control** | No MagSafe on Steam Deck |
| **BIOS-level persistence** | No documented EC interface for charge thresholds |
| **Undervolt/overclock integration** | Out of scope (use PowerTools for that) |
| **Active discharge for calibration** | BMS controls AC/battery path; no `ForceDischarge` D-Bus method |
