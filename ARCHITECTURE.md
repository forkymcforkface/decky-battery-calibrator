# Battery Calibrator — Architecture & Design

This document explains the system architecture, design decisions, and why we made specific choices for Steam Deck battery management.

## Overview

Battery Calibrator is an **event-driven plugin** that manages Steam Deck battery health through charge limiting, calibration cycles, and thermal protection. It uses **zero polling** during normal operation — all updates flow through kernel udev events.

```
┌─────────────────────────────────────────────────┐
│          Battery Calibrator System              │
├─────────────────────────────────────────────────┤
│  Kernel (udevadm monitor)                      │
│           ↓                                     │
│  Python Backend (main.py)                      │
│  ├─ BatteryReader (sysfs)                      │
│  ├─ CalibrationEngine (FSM)                    │
│  ├─ ThermalMonitor (heat protection)           │
│  ├─ ChargeRateControl (0.5-3A)                 │
│  ├─ SettingsManager (JSON persistence)        │
│  └─ CalibrationScheduler (asyncio timer)      │
│           ↓                                     │
│  Decky RPC Bridge                              │
│           ↓                                     │
│  React Frontend (index.tsx)                    │
│  ├─ Dashboard (status, health)                 │
│  ├─ Presets & Profiles                        │
│  ├─ Health Graph (SVG)                        │
│  └─ QAM Widget (quick access)                 │
└─────────────────────────────────────────────────┘
```

## Architecture Principles

### 1. **Event-Driven, Not Polling**

**Problem:** Polling every 100ms for battery status wastes CPU and drains battery.

**Solution:** Use kernel `udevadm monitor --kernel --subsystem-match=power_supply`

```python
# main.py: Listens to kernel events, processes only on change
while True:
    line = await proc.stdout.readline()  # Blocks until battery event
    if b"BAT1" in line and b"change" in line:
        await process_snapshot()  # Only runs on actual change
```

**Fallback:** If udevadm fails (5 consecutive failures), switch to sysfs polling every 5s.

### 2. **State Machine for Calibration**

**Problem:** Calibration is complex — track whether user has unplugged, drained, plugged back in, and charged to 100%. Risk of infinite loops.

**Solution:** Explicit FSM with 5 states:

```
IDLE → UNPLUG_AND_DRAIN → PLUG_IN_AND_CHARGE → COMPLETE
  ↑                                               ↓
  └─────────────────────────────────────────────┘
                  (timeout: TIMED_OUT)
```

Each state transition is explicit. The timeout watchdog prevents getting stuck for >48h.

### 3. **Graceful Degradation**

**Problem:** Steam Deck has multiple charge control interfaces (D-Bus, sysfs). Some may not work on different SteamOS versions.

**Solution:** Factory pattern with automatic fallback:

```python
def create_charge_control() -> ChargeControl:
    try:
        return DBusChargeControl()  # Try D-Bus first (no sudo)
    except:
        return SysfsChargeControl()  # Fall back to sysfs
```

If both fail, the plugin still runs but charge limit commands silently no-op.

### 4. **Async/Await (No Blocking)**

**Problem:** If we block the event loop, the UI freezes and battery updates stop.

**Solution:** Pure asyncio throughout. No blocking I/O:

```python
# ✓ Good: Sleep without blocking
await asyncio.sleep(delay)

# ✓ Good: Wait for subprocess with timeout
line = await asyncio.wait_for(proc.stdout.readline(), timeout=30)

# ✗ Bad: Would freeze the UI
time.sleep(delay)  # Never do this
```

## Core Modules

### `battery.py` — Battery State Reader

Reads from `/sys/class/power_supply/BAT1/`:
- `capacity` — Battery percentage (0-100)
- `status` — Discharging/Charging/Full
- `health` — Battery health (0-100)
- `temp_celsius` — Temperature (from hwmon3)
- `cycle_count` — Number of charge cycles
- `power_watts` — Current power draw

Also reads from `/sys/class/hwmon/hwmon3/`:
- `curr1_input` — USB current (mA) for PD negotiation
- `in0_input` — USB voltage (mV) for PD negotiation

**Why separate module?** Easy to mock in tests, easy to add new sysfs paths.

### `calibration.py` — Calibration FSM

Implements the 5-state machine above. Tracks:
- Current phase
- Start time (for 48h timeout)
- Restore limit (what to set when done)
- Drain threshold (e.g., 5% — when to consider "drained")

**Design decision:** Callbacks instead of blocking methods.

```python
# ✓ This way, callers aren't blocked:
calibration.on_progress(callback)
calibration.on_done(callback)
await calibration.handle_battery_update(snap)  # Async, returns immediately

# ✗ This would block the event loop:
result = await calibration.wait_for_complete()  # Bad!
```

### `charge_control.py` — Charge Limit Control

Two implementations:
1. `DBusChargeControl` — Call `com.steampowered.SteamOSManager1.SetMaxChargeLevel` (no sudo needed)
2. `SysfsChargeControl` — Write to `/sys/class/power_supply/BAT1/max_battery_charge_level` (requires sudo)

**Design decision:** Why D-Bus first?
- D-Bus: No privilege escalation, safer
- Sysfs: Fallback if D-Bus is down (has happened on beta SteamOS)

### `thermal.py` — Heat Protection

Monitors battery temperature from `temp_celsius`. When:
- Temp > 40°C → Set charge limit to 30% (forces EC to stop charging)
- Temp < 38°C → Restore original limit

**Why 40°C / 38°C?**
- Steam Deck battery should stay below 40°C for longevity (industry standard: Li-ion degrades above 40°C)
- 38°C hysteresis prevents rapid on/off thrashing
- 2°C deadband = ~5 minutes of natural cooling

**Why pause at 30%?** Ensures `capacity > limit`, forcing EC to stop (works even if firmware is slow to respond).

### `scheduler.py` — Calibration Scheduler

Schedules next calibration run. Uses pure `asyncio.sleep(seconds_to_next)`:

```python
# ✓ Efficient: calculates seconds until due, sleeps once
await asyncio.sleep(seconds_until_due)
await calibration.start()

# ✗ Inefficient: would poll every minute
while True:
    if time.time() > due_time:
        break
    await asyncio.sleep(60)
```

**Why not a cron job?** Plugin runs in user space, not system. Decky Loader owns the scheduler.

### `history.py` — SQLite Snapshots

Persists battery snapshots for 90 days. Tracks health % over time for trend analysis.

**Schema:**
```sql
snapshots (
  id, timestamp, capacity, health_pct, 
  status, temp_celsius, cycle_count, ...
)
calibrations (
  id, start_time, end_time, phase, result
)
```

**Why SQLite?** Lightweight, queryable, persists across reboots.

## Frontend Architecture

### Why Single File (For Now)?

**Trade-off:** We chose simplicity for v0.1:
- Easier to deploy (no npm bundle issues)
- All state in one React context
- Faster initial development

**Plan:** Split into components in v1.1:
- `BatteryCard.tsx` — Status display
- `HealthChart.tsx` — SVG chart
- `PresetSelector.tsx` — Preset UI
- `CalibrationsPanel.tsx` — History table

### Event Flow

```
Backend Event (e.g., battery update)
  ↓
main.py: self._emit("battery_update", data)
  ↓
Decky RPC Bridge
  ↓
Frontend: addEventListener("battery_update", handler)
  ↓
React setState (triggers re-render)
  ↓
UI Updates
```

**No polling:** Frontend only updates when backend emits.

### Safe RPC Wrapper

All RPC calls wrapped in `safe()`:

```typescript
const safe = async <T,>(fn: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await fn();
  } catch (e) {
    console.error(e);
    return fallback;
  }
};

// Usage:
const status = await safe(
  () => getBatteryStatus(),
  { capacity: null, ... }  // Fallback if RPC fails
);
```

**Why?** If backend crashes, UI stays functional and doesn't show `null` errors.

## Design Decisions & Trade-Offs

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| Event-driven (udevadm) | Zero polling, low CPU | Requires Linux kernel events to work |
| FSM for calibration | Clear state tracking, no infinite loops | Extra complexity for simple flow |
| D-Bus → sysfs fallback | Handles SteamOS version differences | Both need to be tested & maintained |
| SQLite history | Queryable, persistent, lightweight | Adds 1-2MB disk usage |
| Single-file frontend | Faster dev, simpler deploy | Code gets large (924 lines) |
| Safe RPC wrapper | Graceful error handling | Small overhead on every call |
| 5s polling fallback | Balances accuracy vs. CPU | Slower updates if udevadm breaks |

## Known Limitations & Future Work

See `KNOWN_LIMITATIONS.md` for detailed constraints.

**Future improvements (v1.1+):**
- [ ] Refactor frontend into components
- [ ] Add integration tests for concurrent scenarios
- [ ] Support custom charge thresholds per profile
- [ ] Export history as CSV/JSON
- [ ] Theme-aware colors (dark/light mode)

## Testing Strategy

### Unit Tests (167 tests, all passing)
- Mock BatteryReader, ChargeControl, etc.
- Verify FSM state transitions
- Test callbacks
- Test async timeouts

### Integration Tests (Planned)
- Real battery snapshots from Steam Deck
- Concurrent calibration + heat protection
- Rapid battery event handling

### Manual Testing (Done)
- Tested on real Steam Deck (Stable SteamOS)
- Verified charge limit via `SetMaxChargeLevel`
- Verified sysfs fallback
- Verified heat protection triggers

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Memory (idle) | 28-30 MB |
| Memory (peak) | 35-40 MB |
| CPU (idle) | 0.0% (blocked on udevadm read) |
| CPU (battery event) | <1% for 100ms |
| RPC latency | 50-200ms |
| SQLite insert | 5-10ms |
| History retention | 90 days (configurable) |

## Debugging

Enable debug logging in `main.py`:

```python
decky.logger.debug("Message")
# View logs:
# journalctl -u decky-loader -f | grep "Battery Calibrator"
```

Check battery state directly:

```bash
cat /sys/class/power_supply/BAT1/capacity
cat /sys/class/hwmon/hwmon3/temp1_input  # In millidegrees
udevadm monitor --kernel --subsystem-match=power_supply
```

Test D-Bus charge control:

```bash
busctl --system call com.steampowered.SteamOSManager1 \
  /com/steampowered/SteamOSManager1 \
  com.steampowered.SteamOSManager1.RootManager SetMaxChargeLevel i 80
```

## References

- [AlDente](https://apphousekitchen.com/) — Inspiration for charge limiting
- [Steam Deck hwmon](https://github.com/ValveSoftware/SteamDeck-Hardware-Reference-Files)
- [Linux power supply sysfs](https://www.kernel.org/doc/html/latest/power/power_supply_class.html)
- [asyncio best practices](https://docs.python.org/3/library/asyncio.html)
