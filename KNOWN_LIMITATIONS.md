# Battery Calibrator — Known Limitations & Constraints

This document explains what Battery Calibrator **cannot** do, and why.

## Hardware Limitations (Steam Deck EC Firmware)

### ❌ Cannot Discharge While Plugged In

**What:** You cannot force the battery to discharge while the charger is connected.

**Why:** The EC (Embedded Controller) firmware doesn't expose a `ForceDischarge` D-Bus method. This is a firmware limitation, not a software bug.

**Implication:** Calibration requires:
1. Unplug the charger
2. Use the battery until it drains to your threshold (e.g., 5%)
3. Plug back in and charge to 100%

There's no way to bypass this.

**References:**
- Steam Deck Hardware Reference: No documented EC interface for forced discharge
- Valve issue tracking: No ETA for firmware update

### ❌ Cannot Directly Control EC Charging Algorithm

**What:** You cannot tell the EC "start charging now" or "stop in 5 minutes."

**Why:** The EC only accepts a single parameter: `max_battery_charge_level` (or via sysfs).

**Implication:**
- Charge limit is a threshold, not a timer
- If limit is 80%, the EC will charge to 80% whenever plugged in
- You cannot schedule charging for a specific time (e.g., "charge from 2-3 AM")

### ❌ No MagSafe or Advanced Features

**What:** Steam Deck doesn't have MagSafe, wireless charging, or bidirectional charging.

**Why:** Hardware doesn't exist.

**Implication:** Features like "export power to phone" or "wireless charging profiles" are impossible.

## Software Limitations

### ⚠️ udevadm Monitor May Fail on Some Setups

**What:** Battery Calibrator uses `udevadm monitor` for event-driven updates.

**Why:** This works on most Steam Decks (Stable & Beta SteamOS), but can fail due to:
- Kernel seccomp filters blocking subprocess communication
- SteamOS kernel lock-down mode
- Unusual asyncio configurations

**Fallback:** After 5 udevadm failures, falls back to sysfs polling every 5 seconds.

**Impact:**
- Same functionality (no features lost)
- Updates slower (5s instead of <100ms)
- Slightly higher CPU usage (~0.1% vs. 0.0%)

**Status:** On production Steam Decks, udevadm always works. Fallback is for edge cases.

### ⚠️ Sysfs Paths May Vary

**What:** Battery and hwmon sysfs paths can differ by Steam Deck revision.

**Expected paths:**
- `/sys/class/power_supply/BAT1/` — Primary battery
- `/sys/class/hwmon/hwmon3/` — Temperature and PD power

**What if paths differ?** The plugin will fail to read battery status.

**Mitigation:** We detect missing files and skip features gracefully (no crashes).

**Future fix:** Scan `/sys/class/power_supply/` and `/sys/class/hwmon/` for available devices.

### ⚠️ D-Bus May Not Work on Preview SteamOS

**What:** D-Bus `SetMaxChargeLevel` is the preferred charge control method (no sudo).

**Status:**
- ✓ Works on Stable & Beta SteamOS
- ❓ Unknown on Preview SteamOS (untested)
- ✓ Sysfs fallback always works (requires sudo)

**Mitigation:** The plugin automatically falls back to sysfs if D-Bus fails.

### ⚠️ Charge Limit Sudo Requirement (Sysfs Path)

**What:** Writing to `/sys/class/power_supply/BAT1/max_battery_charge_level` requires sudo.

**Why:** It's a privileged sysfs file (mode 0644 owned by root).

**Solution:** Decky Loader runs under special permissions. This "just works."

**Implication:** If someone runs this plugin outside Decky Loader, it won't work without sudo.

## Feature Limitations

### ❌ Calibration is Slow

**What:** Automated calibration cycles take 2-48 hours (depending on drain threshold).

**Why:** Battery discharge is slow. Even at 100% load, a 50Wh battery at 5W load takes ~10 hours to drain.

**Implication:**
- Schedule calibration during storage or travel (not before gaming)
- Default interval: 14 days
- Minimum interval: 7 days (you choose in settings)

### ⚠️ Heat Protection Has Limitations

**What:** When battery temp > 40°C, charging pauses by setting limit to 30%.

**Doesn't prevent:**
- Ambient heat from gaming (30% limit doesn't cool the battery)
- Throttling due to SoC heat (separate from battery)
- Thermal runaway (won't happen on Steam Deck, but firmware has hard limits)

**Recommendation:** Use in well-ventilated areas. If you're gaming in a hot room, heat protection won't save you — stop gaming or get airflow.

### ⚠️ Smart Charge Cycles Can Interfere

**What:** "Smart charge" auto-cycles between min/max (e.g., 30–80%).

**Limitations:**
- Disabled during calibration (no conflicts)
- Disabled during top-up (no conflicts)
- But if you manually change limit while active, behavior is undefined

**Recommendation:** If you toggle "Smart charge" on/off, wait 10 seconds for state sync.

### ❌ No Charging Schedule (e.g., Charge 2-4 AM)

**What:** You cannot tell Battery Calibrator "only charge at night."

**Why:** Steam Deck EC doesn't support scheduled charging.

**Workaround:** Manually unplug when you reach your limit, plug back in during off-peak hours.

### ⚠️ Profiles Don't Persist Across Updates

**What:** If you save a profile and the plugin updates, the profile is still there.

**But:** If you clear plugin settings (Settings → Decky → Clear Battery Calibrator Data), profiles are deleted.

**Recommendation:** Screenshot your profiles before clearing settings, or just reconfigure (only takes ~30 seconds).

## Testing Limitations

### ⚠️ No Integration Tests on Hardware

**What:** Tests are unit tests with mocks.

**Why:** Can't hook real battery events in a test environment.

**Implication:**
- Tests verify logic correctness (great)
- But don't test real Steam Deck battery behavior (limitation)

**Mitigation:** Manual testing on real hardware (done for this release).

### ⚠️ Limited Testing on SteamOS Versions

**Tested on:**
- ✓ SteamOS Stable (6.11 kernel)
- ❓ SteamOS Beta (untested, should work)
- ❓ SteamOS Preview (untested, needs testing)

**Recommendation:** If you're on Preview, test before relying on this plugin.

## Performance Limitations

### ⚠️ History Database Grows Over Time

**What:** Battery Calibrator stores snapshots every ~30s (during events).

**Size:** ~1KB per snapshot = ~100MB per year

**Mitigation:** Automatic pruning at 90 days (default, configurable).

**Manual cleanup:** Delete `/home/deck/.config/decky-battery-calibrator/history.db`

### ⚠️ Large Health Graphs Slow Down Rendering

**What:** If you have 3+ months of history, the SVG chart gets large.

**Impact:** Chart takes 100-200ms to render (you'll see a brief stutter).

**Mitigation:** We prune history automatically. Worst case: delete old data via settings.

## Workarounds & Recommendations

| Limitation | Workaround |
|-----------|-----------|
| **Slow discharge** | Set drain threshold to 10-15% instead of 1-5% |
| **Heat protection insufficient** | Use in cool environment, increase airflow |
| **Smart charge interference** | Don't toggle it rapidly; wait 10s between changes |
| **No charging schedule** | Manually unplug/replug at desired times |
| **Profile lost on clear** | Screenshot settings before clearing data |
| **udevadm fails** | Plugin auto-falls back to polling (no action needed) |
| **Sysfs paths differ** | Report issue with output of `ls /sys/class/power_supply/` |

## Reporting Issues

If you hit a limitation or find a bug:

1. **Check this file first** — You might be hitting a known limitation
2. **Gather logs:**
   ```bash
   journalctl -u decky-loader -n 100 > /tmp/battery-log.txt
   cat /sys/class/power_supply/BAT1/capacity > /tmp/battery-state.txt
   ```
3. **Open an issue:** https://github.com/Yogendra96/decky-battery-calibrator/issues
   - Include SteamOS version (Settings → System)
   - Include logs above
   - Describe exact steps to reproduce

## Future Possibilities (v1.1+)

- [ ] Support `/sys/class/power_supply/BAT0` (if it exists on some units)
- [ ] Test on SteamOS Beta/Preview
- [ ] Integration tests with mock battery data
- [ ] Export history as CSV for analysis
- [ ] Custom charge thresholds per profile
- [ ] Scheduled maintenance calibration

