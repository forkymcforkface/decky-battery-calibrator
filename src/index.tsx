import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  staticClasses,
  DropdownItem,
  ToggleField,
} from "@decky/ui";
import {
  addEventListener,
  removeEventListener,
  callable,
  definePlugin,
  toaster,
  routerHook,
  useQuickAccessVisible,
} from "@decky/api"
import { useState, useEffect } from "react";
import { FaBatteryThreeQuarters, FaTimesCircle, FaExclamationTriangle, FaInfoCircle } from "react-icons/fa";
import { HealthChart } from "./components/HealthChart";
import { PresetSelector } from "./components/PresetSelector";

const getBatteryStatus = callable<[], {
  capacity: number | null;
  status: string;
  ac_connected: boolean;
  charge_limit: number | null;
  health: number | null;
  cycle_count: number | null;
  power_watts: number | null;
  voltage: number | null;
  current: number | null;
  charge_full: number | null;
  charge_full_design: number | null;
  charge_rate_available: boolean;
  charge_rate_amps: number | null;
  temp_celsius: number | null;
  thermal_throttled: boolean;
}>("get_battery_status");

const setChargeLimit = callable<[percent: number], boolean>("set_charge_limit");

const getNextCalibration = callable<[], {
  next_calibration: string;
  interval_days: number;
  last_calibration: string | null;
}>("get_next_calibration");

const startCalibration = callable<[], boolean>("start_calibration");
const cancelCalibration = callable<[], void>("cancel_calibration");
const snoozeCalibration = callable<[days: number], void>("snooze_calibration");
const getCalibrationState = callable<[], { phase: string; active: boolean }>("get_calibration_state");
const getSettings = callable<[], Record<string, unknown>>("get_settings");
const updateSettings = callable<[updates: Record<string, unknown>], void>("update_settings");

const getPresets = callable<[], { built_in: Record<string, number>; custom: Record<string, number> }>("get_presets");
const applyPreset = callable<[name: string], boolean>("apply_preset");
const pauseCharging = callable<[], boolean>("pause_charging");
const topUp = callable<[], boolean>("top_up");
const getChargeRate = callable<[], { available: boolean; microamps: number; amps: number }>("get_charge_rate");
const setChargeRateLimit = callable<[microamps: number], boolean>("set_charge_rate");

const getHistory = callable<[], { snapshots: any[]; calibrations: any[] }>("get_history");
const getSailingMode = callable<[], { enabled: boolean; low: number; high: number }>("get_sailing_mode");

const saveProfile = callable<[name: string], void>("save_profile");
const loadProfile = callable<[name: string], boolean>("load_profile");
const deleteProfile = callable<[name: string], void>("delete_profile");
const getProfiles = callable<[], Record<string, Record<string, unknown>>>("get_profiles");

const EXTENDED_MIN = 20;
const NORMAL_MIN = 50;
const RATE_MAX = 3000000;
const RATE_MIN = 500000;
const RATE_STEP = 250000;

function InfoTip({ text }: { text: string }) {
  return (
    <span
      style={{ display: "inline-flex", alignItems: "center", marginLeft: "4px", verticalAlign: "middle", cursor: "help" }}
      title={text}
    >
      <FaInfoCircle size={12} color="#888" />
    </span>
  );
}

function ProgressBar({ value, color }: { value: number; color: string }) {  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div style={{
      height: "16px", background: "rgba(255,255,255,0.1)", borderRadius: "8px",
      overflow: "hidden", position: "relative",
    }}>
      <div style={{
        width: `${pct}%`, height: "100%", background: color, borderRadius: "8px",
        transition: "width 0.5s ease",
      }} />
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "11px", fontWeight: "bold", color: "white",
      }}>
        {pct}%
      </div>
    </div>
  );
}

function BatteryWidget() {
  const visible = useQuickAccessVisible();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (!visible) return;
    getBatteryStatus().then(setData).catch(() => {});

    const onUpdate = addEventListener<[data: any]>("battery_update", setData);
    return () => { removeEventListener("battery_update", onUpdate); };
  }, [visible]);

  if (!visible) return null;

  const cap = data?.capacity;
  const status = data?.status;
  let batColor = "#aaa";
  if (status === "Charging") batColor = "#4ade80";
  else if (status === "Discharging") batColor = "#facc15";
  else if (cap != null && cap <= 20) batColor = "#ef4444";

  const handlePause = async () => {
    await pauseCharging();
    getBatteryStatus().then(setData);
  };

  return (
    <div style={{
      padding: "8px 12px", margin: "4px 8px", borderRadius: "8px",
      background: "rgba(255,255,255,0.05)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <FaBatteryThreeQuarters size={20} color={batColor} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
            <span style={{ fontSize: "18px", fontWeight: "bold", color: batColor }}>
              {cap != null ? `${cap}%` : "--"}
            </span>
            <span style={{ fontSize: "11px", color: batColor }}>● {status}</span>
          </div>
          <div style={{ fontSize: "11px", color: "#888" }}>
            {data?.charge_limit != null && (
              <span>Limit: {data.charge_limit}%</span>
            )}
            {data?.power_watts != null && (
              <span> · {data.power_watts} W</span>
            )}
            {data?.temp_celsius != null && (
              <span> · {data.temp_celsius}°C</span>
            )}
            {data?.ac_connected && data?.pd_watts != null && (
              <span> · {data.pd_watts} W in</span>
            )}
          </div>
        </div>
        <button onClick={handlePause} style={{
          padding: "4px 10px", borderRadius: "4px", border: "1px solid rgba(255,255,255,0.2)",
          background: "rgba(255,255,255,0.1)", color: "white", fontSize: "11px", cursor: "pointer",
        }}>
          Pause
        </button>
      </div>
    </div>
  );
}

function Content() {
  const [battery, setBattery] = useState<any>(null);
  const [calInfo, setCalInfo] = useState<any>(null);
  const [calState, setCalState] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [limit, setLimit] = useState<number>(80);
  const [presets, setPresets] = useState<Record<string, Record<string, number>>>({ built_in: {}, custom: {} });
  const [chargeRate, setChargeRate] = useState<number>(2000000);
  const [extendedRange, setExtendedRange] = useState<boolean>(false);
  const [rateAvailable, setRateAvailable] = useState<boolean>(false);
  const [history, setHistory] = useState<{ snapshots: any[]; calibrations: any[] }>({ snapshots: [], calibrations: [] });
  const [sailingMode, setSailingMode] = useState<{ enabled: boolean; low: number; high: number }>({ enabled: false, low: 70, high: 80 });
  const [chartWidth, setChartWidth] = useState<number>(300);
  const [smartMin, setSmartMin] = useState<number>(30);
  const [smartMax, setSmartMax] = useState<number>(80);
  const [profiles, setProfiles] = useState<Record<string, Record<string, unknown>>>({});
  const [profileName, setProfileName] = useState<string>("");
  const [quietCharging, setQuietCharging] = useState<boolean>(false);

  const refresh = async () => {
    const safe = async <T,>(fn: () => Promise<T>, fallback: T): Promise<T> => {
      try { return await fn(); } catch { return fallback; }
    };
    const [b, c, cs, s, p, r, h, sm, pr] = await Promise.all([
      safe(getBatteryStatus, null),
      safe(getNextCalibration, null),
      safe(getCalibrationState, null),
      safe(getSettings, null),
      safe(getPresets, { built_in: {}, custom: {} }),
      safe(getChargeRate, null),
      safe(getHistory, { snapshots: [], calibrations: [] }),
      safe(getSailingMode, { enabled: false, low: 70, high: 80 }),
      safe(getProfiles, {}),
    ]);
    setBattery(b ?? null);
    setCalInfo(c ?? null);
    setCalState(cs ?? null);
    setSettings(s ?? null);
    setPresets(p ?? { built_in: {}, custom: {} });
    setHistory(h ?? { snapshots: [], calibrations: [] });
    setSailingMode(sm ?? { enabled: false, low: 70, high: 80 });
    setProfiles(pr ?? {});
    if (b?.charge_limit) setLimit(b.charge_limit);
    if (r?.available) {
      setRateAvailable(true);
      if (r.microamps > 0) setChargeRate(r.microamps);
    }
    if (s?.extended_range_enabled) setExtendedRange(true);
    if (s?.smart_charge_min) setSmartMin(s.smart_charge_min as number);
    if (s?.smart_charge_max) setSmartMax(s.smart_charge_max as number);
    if (s?.quiet_charging_enabled !== undefined) setQuietCharging(s.quiet_charging_enabled as boolean);
  };

  useEffect(() => {
    refresh();

    const onBatteryUpdate = addEventListener<[data: any]>(
      "battery_update", (data) => {
        setBattery(data);
        if (data?.charge_limit) setLimit(data.charge_limit);
      }
    );

    const onProgress = addEventListener<[stage: string, cap: number | null]>(
      "calibration_progress", () => refresh()
    );
    const onDone = addEventListener<[result: string]>(
      "calibration_done", () => {
        toaster.toast({ title: "Battery Calibrator", body: "Calibration complete!" });
        refresh();
      }
    );
    const onDue = addEventListener<[]>(
      "calibration_due", () => {
        toaster.toast({ title: "Battery Calibrator", body: "Calibration is due! Open plugin to start." });
      }
    );
    const onTopUpDone = addEventListener<[]>(
      "top_up_done", () => {
        toaster.toast({ title: "Battery Calibrator", body: "Top-up complete! Limit restored." });
        refresh();
      }
    );

    return () => {
      removeEventListener("battery_update", onBatteryUpdate);
      removeEventListener("calibration_progress", onProgress);
      removeEventListener("calibration_done", onDone);
      removeEventListener("calibration_due", onDue);
      removeEventListener("top_up_done", onTopUpDone);
    };
  }, []);

  const handleLimit = async (val: number) => {
    setLimit(val);
    await setChargeLimit(val);
  };

  const handleCalibrate = async () => {
    const ok = await startCalibration();
    if (ok) {
      toaster.toast({
        title: "Battery Calibrator",
        body: "Limit set to 100%. Unplug and drain below 30%, then recharge to 100%."
      });
    }
    refresh();
  };

  const handleCancel = async () => {
    await cancelCalibration();
    toaster.toast({ title: "Battery Calibrator", body: "Calibration cancelled." });
    refresh();
  };

  const handleSnooze = async (opt: { data: number }) => {
    await snoozeCalibration(opt.data);
    const d = opt.data;
    toaster.toast({ title: "Battery Calibrator", body: `Snoozed for ${d} day${d > 1 ? "s" : ""}.` });
    refresh();
  };

  const handleIntervalChange = async (opt: { data: number }) => {
    await updateSettings({ calibration_interval_days: opt.data });
    refresh();
  };

  const handlePreset = async (opt: { data: string }) => {
    const ok = await applyPreset(opt.data);
    if (ok) {
      toaster.toast({ title: "Battery Calibrator", body: `Preset "${opt.data}" applied.` });
      refresh();
    }
  };

  const handlePause = async () => {
    const ok = await pauseCharging();
    if (ok) {
      toaster.toast({ title: "Battery Calibrator", body: "Paused at current capacity." });
      refresh();
    }
  };

  const handleTopUp = async () => {
    const ok = await topUp();
    if (ok) {
      toaster.toast({ title: "Battery Calibrator", body: "Charging to 100%. Limit will be restored automatically." });
      refresh();
    }
  };

  const handleExtendedRange = async (val: boolean) => {
    setExtendedRange(val);
    await updateSettings({ extended_range_enabled: val });
  };

  const handleRateChange = async (val: number) => {
    setChargeRate(val);
    await setChargeRateLimit(val);
  };

  const handleSailingMode = async (val: boolean) => {
    await updateSettings({ sailing_mode_enabled: val });
    refresh();
  };

  const handleSmartCharge = async (val: boolean) => {
    await updateSettings({ smart_charge_enabled: val });
    refresh();
  };

  const handleQuietCharging = async (val: boolean) => {
    await updateSettings({ quiet_charging_enabled: val });
    refresh();
  };

  const handleSmartMin = async (val: number) => {
    setSmartMin(val);
    await updateSettings({ smart_charge_min: val });
  };

  const handleSmartMax = async (val: number) => {
    setSmartMax(val);
    await updateSettings({ smart_charge_max: val });
  };

  const handleSaveProfile = async () => {
    const name = profileName.trim();
    if (!name) return;
    await saveProfile(name);
    toaster.toast({ title: "Battery Calibrator", body: `Profile "${name}" saved.` });
    refresh();
  };

  const handleLoadProfile = async (opt: { data: string }) => {
    const ok = await loadProfile(opt.data);
    if (ok) {
      toaster.toast({ title: "Battery Calibrator", body: `Profile "${opt.data}" loaded.` });
      refresh();
    }
  };

  const handleDeleteProfile = async () => {
    const name = profileName.trim();
    if (!name) return;
    await deleteProfile(name);
    toaster.toast({ title: "Battery Calibrator", body: `Profile "${name}" deleted.` });
    setProfileName("");
    refresh();
  };

  const cap = battery?.capacity;
  const status = battery?.status;
  const phase = calState?.phase;
  const active = calState?.active;
  const isDraining = phase === "unplug_and_drain";
  const isCharging = phase === "plug_in_charge" || phase === "plug_in_and_charge";
  const isTimedOut = phase === "timed_out";
  const sailing = sailingMode?.enabled;

  let batColor = "white";
  if (status === "Charging") batColor = "#4ade80";
  else if (status === "Discharging") batColor = "#facc15";
  else if (cap != null && cap <= 20) batColor = "#ef4444";

  let calProgress = 0;
  let calColor = "#4ade80";
  let calLabel = "";
  if (isDraining) {
    const drainTarget = settings?.calibration_drain_threshold ?? 30;
    calProgress = cap != null && cap > drainTarget
      ? (100 - cap) / (100 - drainTarget)
      : 1;
    calColor = "#facc15";
    calLabel = "Draining battery";
  } else if (isCharging) {
    calProgress = cap != null ? cap / 100 : 0;
    calColor = "#4ade80";
    calLabel = "Charging to 100%";
  }

  const sliderMin = extendedRange ? EXTENDED_MIN : NORMAL_MIN;
  const sliderNotchCount = Math.floor((100 - sliderMin) / 5) + 1;

  const rateLabel = chargeRate > 0
    ? `${(chargeRate / 1e6).toFixed(2)} A`
    : "No limit";

  const chartData = (history?.snapshots ?? [])
    .filter((s: any) => s.health_pct !== null)
    .map((s: any) => ({ recorded_at: s.recorded_at, health_pct: s.health_pct }));

  const calLog = history?.calibrations || [];

  return (
    <PanelSection title="Battery">
      {sailing && (
        <PanelSectionRow>
          <div style={{
            display: "flex", alignItems: "center", gap: "8px", color: "#60a5fa",
            fontSize: "12px", padding: "4px 8px", background: "rgba(96,165,250,0.1)", borderRadius: "4px",
          }}>
            <FaBatteryThreeQuarters size={14} />
            Sailing mode — limit set to {sailingMode.low}% for long-term storage
          </div>
        </PanelSectionRow>
      )}

      <PanelSectionRow>
        <div style={{
          display: "flex", alignItems: "center", gap: "12px", padding: "8px",
          background: "rgba(255,255,255,0.05)", borderRadius: "8px",
        }}>
          <FaBatteryThreeQuarters size={28} color={batColor} />
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ fontSize: "24px", fontWeight: "bold", color: batColor }}>
                {cap != null ? `${cap}%` : "--"}
              </span>
              <span style={{ fontSize: "13px", color: batColor }}>
                ● {status ?? "--"}
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "#999" }}>
              {battery?.ac_connected ? "Plugged in" : "On battery"}
              {battery?.power_watts != null && (
                <span> · {battery.power_watts} W</span>
              )}
              {battery?.voltage != null && (
                <span> · {(battery.voltage / 1e6).toFixed(3)} V</span>
              )}
              {battery?.current != null && (
                <span> · {(battery.current / 1e6).toFixed(0)} mA</span>
              )}
              {battery?.temp_celsius != null && (
                <span> · {battery.temp_celsius}°C</span>
              )}
            </div>
          </div>
          {battery?.thermal_throttled && (
            <div style={{ color: "#f97316" }} title="Thermal throttling active">
              <FaExclamationTriangle size={18} />
            </div>
          )}
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <SliderField
          label="Charge limit"
          description={`${battery?.charge_limit ?? "--"}%`}
          value={limit}
          min={sliderMin}
          max={100}
          step={5}
          onChange={handleLimit}
          notchCount={sliderNotchCount}
          notchLabels={[
            { notchIndex: 0, label: `${sliderMin}` },
            ...(extendedRange ? [{ notchIndex: Math.round((80 - sliderMin) / 5), label: "80" }] : []),
            { notchIndex: sliderNotchCount - 1, label: "100" },
          ]}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Sets the maximum charge level. Battery won't charge above this percentage. Lower = longer lifespan." />
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Extended range"
          description="Allow charge limit down to 20%"
          checked={extendedRange}
          onChange={handleExtendedRange}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Extends the slider down to 20%. Deeper discharge cycles can accelerate battery wear — use only when needed." />
        </div>
      </PanelSectionRow>

      {presets.built_in && Object.keys(presets.built_in).length > 0 && (
        <PanelSectionRow>
          <PresetSelector presets={presets} onApply={handlePreset} />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Quick-apply a preconfigured charge limit. Built-in presets: Storage (60%), Normal (80%), Full (100%), Travel (95%)." />
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem layout="below" onClick={handlePause}>
          Pause
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={handleTopUp}>
          Top up
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Pause: sets limit to current capacity, stopping any further charging. Top up: temporarily charges to 100%, then auto-restores your limit when full." />
        </div>
      </PanelSectionRow>

      {battery && (
        <PanelSectionRow>
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px 16px",
            fontSize: "12px", color: "#999", padding: "4px 0",
          }}>
            {battery.health != null && <div>Health: {battery.health}%</div>}
            {battery.cycle_count != null && <div>Cycles: {battery.cycle_count}</div>}
            {battery.charge_full != null && (
              <div>Full: {(battery.charge_full / 1e6).toFixed(0)} mAh</div>
            )}
            {battery.charge_full_design != null && battery.charge_full_design !== battery.charge_full && (
              <div>Design: {(battery.charge_full_design / 1e6).toFixed(0)} mAh</div>
            )}
            {battery.charge_rate_available && battery.charge_rate_amps != null && (
              <div>Rate: {battery.charge_rate_amps.toFixed(2)} A</div>
            )}
            {battery.temp_celsius != null && <div>Temp: {battery.temp_celsius}°C</div>}
            {battery.ac_connected && battery.pd_watts != null && (
              <div>Input: {battery.pd_watts} W</div>
            )}
          </div>
        </PanelSectionRow>
      )}

      {rateAvailable && !quietCharging && (
        <PanelSectionRow>
          <SliderField
            label="Charge rate"
            description={rateLabel}
            value={chargeRate}
            min={RATE_MIN}
            max={RATE_MAX}
            step={RATE_STEP}
            onChange={handleRateChange}
            notchCount={Math.floor((RATE_MAX - RATE_MIN) / RATE_STEP) + 1}
            notchLabels={[
              { notchIndex: 0, label: "0.5A" },
              { notchIndex: Math.floor((RATE_MAX - RATE_MIN) / RATE_STEP / 2), label: "1.75A" },
              { notchIndex: Math.floor((RATE_MAX - RATE_MIN) / RATE_STEP), label: "3A" },
            ]}
          />
        </PanelSectionRow>
      )}
      {rateAvailable && quietCharging && (
        <PanelSectionRow>
          <div style={{ fontSize: "12px", color: "#999", padding: "8px 0" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Charge rate</span>
              <span>0.50 A (quiet)</span>
            </div>
            {battery?.ac_connected && battery.power_watts != null && (
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2px" }}>
                <span>Battery</span>
                <span>{battery.power_watts} W</span>
              </div>
            )}
            {battery?.ac_connected && battery.pd_watts != null && (
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2px" }}>
                <span>Charger</span>
                <span>{battery.pd_watts} W</span>
              </div>
            )}
          </div>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Limits charging current. Lower = cooler but slower. Quiet mode locks to 0.5A independent of this slider. Heat protection (if enabled) auto-reduces when battery exceeds the temperature threshold." />
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Quiet charging"
          description="Always cap at 0.5A for minimal heat and fan noise"
          checked={quietCharging}
          onChange={handleQuietCharging}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="Limits charge rate to 0.5A (3.85W) regardless of temperature. Minimal charging heat, fan runs quieter. Ideal for overnight charging or low-impact desktop use." />
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Sailing mode"
          description="Long-term storage mode (limit at 70%)"
          checked={sailing}
          onChange={handleSailingMode}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="For long-term storage. Sets charge limit to 70% and disables calibration scheduling. Best for storing the Deck unused for weeks." />
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Smart charge"
          description={`Auto-cycle between ${smartMin}% and ${smartMax}%`}
          checked={settings?.smart_charge_enabled ?? false}
          onChange={handleSmartCharge}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "11px", color: "#666" }}>
          <InfoTip text="When enabled, the limit auto-adjusts: charges to the max %, then pauses until it naturally drains to the min %. Keeps your battery in the ideal range through normal use." />
        </div>
      </PanelSectionRow>

      {(settings?.smart_charge_enabled) && (
        <>
          <PanelSectionRow>
            <SliderField
              label="Min charge"
              description={`${smartMin}%`}
              value={smartMin}
              min={10}
              max={smartMax - 10}
              step={5}
              onChange={handleSmartMin}
              notchCount={Math.floor((smartMax - 10 - 10) / 5) + 1}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField
              label="Max charge"
              description={`${smartMax}%`}
              value={smartMax}
              min={smartMin + 10}
              max={95}
              step={5}
              onChange={handleSmartMax}
              notchCount={Math.floor((95 - (smartMin + 10)) / 5) + 1}
            />
          </PanelSectionRow>
        </>
      )}

      <PanelSection title="Profiles">
        <PanelSectionRow>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <input
              type="text"
              placeholder="Profile name"
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
              style={{
                flex: 1, padding: "6px 8px", borderRadius: "4px", border: "1px solid rgba(255,255,255,0.2)",
                background: "rgba(255,255,255,0.05)", color: "white", fontSize: "14px",
              }}
            />
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleSaveProfile}>
            Save
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleDeleteProfile}>
            Delete
          </ButtonItem>
        </PanelSectionRow>
        {Object.keys(profiles ?? {}).length > 0 && (
          <PanelSectionRow>
            <DropdownItem
              label="Load"
              description="Restore a saved profile"
              rgOptions={Object.keys(profiles ?? {}).map((name) => ({ data: name, label: name }))}
              selectedOption={""}
              onChange={handleLoadProfile}
            />
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Schedule">
        <PanelSectionRow>
          <DropdownItem
            label="Every"
            description="Days between calibration cycles"
            rgOptions={[
              { data: 7, label: "7 days (weekly)" },
              { data: 14, label: "14 days (biweekly)" },
              { data: 21, label: "21 days (3 weeks)" },
              { data: 30, label: "30 days (monthly)" },
            ]}
            selectedOption={settings?.calibration_interval_days ?? 14}
            onChange={handleIntervalChange}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Snooze"
            description="Postpone the next calibration"
            rgOptions={[
              { data: 1, label: "1 day" },
              { data: 3, label: "3 days" },
              { data: 7, label: "7 days" },
              { data: 14, label: "14 days" },
            ]}
            selectedOption={-1}
            onChange={handleSnooze}
          />
        </PanelSectionRow>
        {calInfo && (
          <PanelSectionRow>
            <div style={{
              fontSize: "12px", color: "#999", padding: "4px 0",
              display: "flex", gap: "16px",
            }}>
              <span>Next: {calInfo?.next_calibration ? new Date(calInfo.next_calibration).toLocaleDateString() : "--"}</span>
              <span>Last: {calInfo?.last_calibration ? new Date(calInfo.last_calibration).toLocaleDateString() : "never"}</span>
            </div>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Action">
        {active ? (
          <>
            {calLabel && (
              <PanelSectionRow>
                <ProgressBar value={calProgress} color={calColor} />
              </PanelSectionRow>
            )}
            <PanelSectionRow>
              <div style={{
                fontSize: "12px", color: "#999", padding: "4px 0",
              }}>
                {isDraining
                  ? "Unplug AC power and let the battery drain below 30%."
                  : "Plug in AC power and wait for the battery to reach 100%."}
              </div>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={handleCancel}>
                Cancel calibration
              </ButtonItem>
            </PanelSectionRow>
          </>
        ) : (
          <>
            {isTimedOut && (
              <PanelSectionRow>
                <div style={{
                  display: "flex", alignItems: "center", gap: "8px", color: "#ef4444",
                  fontSize: "12px", padding: "4px 0",
                }}>
                  <FaTimesCircle />
                  Calibration timed out (48h limit). Start a fresh cycle when you can complete it in one session.
                </div>
              </PanelSectionRow>
            )}
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={handleCalibrate}>
                Start calibration cycle
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <div style={{ fontSize: "11px", color: "#666" }}>
                <InfoTip text="Full discharge→recharge cycle to keep the fuel gauge accurate. Unplug and let it drain below 30%, then plug back in and wait for 100%. The limit is restored automatically. Run every 14 days." />
              </div>
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      {chartData.length > 0 && (
        <PanelSection title="Health History">
          <PanelSectionRow>
            <div ref={(el) => { if (el) setChartWidth(el.clientWidth); }}>
              <HealthChart data={chartData} width={chartWidth || 300} height={140} />
            </div>
          </PanelSectionRow>
        </PanelSection>
      )}

      {calLog.length > 0 && (
        <PanelSection title="Calibration Log">
          {calLog.map((log: any, i: number) => (
            <PanelSectionRow key={i}>
              <div style={{
                display: "flex", justifyContent: "space-between", fontSize: "12px",
                color: log.result === "success" ? "#4ade80" : log.result === "timed_out" ? "#ef4444" : "#999",
                padding: "2px 0",
              }}>
                <span>{new Date(log.started_at).toLocaleDateString()}</span>
                <span>{log.result || "in progress"}</span>
              </div>
            </PanelSectionRow>
          ))}
        </PanelSection>
      )}
    </PanelSection>
  );
};

export default definePlugin(() => {
  const WIDGET_NAME = "battery-calibrator-widget";
  routerHook.addGlobalComponent(WIDGET_NAME, BatteryWidget);

  return {
    name: "Battery Calibrator",
    titleView: <div className={staticClasses.Title}>Battery Calibrator</div>,
    content: <Content />,
    icon: <FaBatteryThreeQuarters />,
    alwaysRender: true,
    onDismount() {
      routerHook.removeGlobalComponent(WIDGET_NAME);
    },
  };
});
