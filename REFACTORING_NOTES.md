# Frontend Refactoring Plan (v0.1.0 → v1.1)

## Current State
- Single `src/index.tsx`: 924 lines
- All components in one file
- Works fine but hard to maintain

## Planned Split (v1.1)

```
src/
├── index.tsx                    # Main entry point, routing
├── hooks/
│   └── useAutoRefresh.ts       # Re-sync with backend on interval
├── components/
│   ├── BatteryCard.tsx         # Status display (capacity, temp, health)
│   ├── HealthChart.tsx         # SVG trend graph
│   ├── PresetSelector.tsx      # Preset UI
│   ├── CalibrationsPanel.tsx   # History table
│   ├── SettingsPanel.tsx       # Charge limit, rate, heat protection sliders
│   ├── ProfileManager.tsx      # Save/load/delete profiles
│   └── InfoTip.tsx             # Reusable tooltip icon
└── types.d.ts                  # Decky type definitions
```

## Why Wait Until v1.1?

1. **Stability first** — v0.1.0 works as single file, users need it now
2. **Proven design** — Once users report how they use it, we can structure for real needs
3. **Build complexity** — Splitting requires fixing TypeScript module imports
4. **Testing** — Component tests add complexity, better after MVP

## v1.1 Implementation Steps

1. Extract `InfoTip` → `components/InfoTip.tsx`
2. Extract `HealthChart` → `components/HealthChart.tsx`
3. Extract `ProgressBar` → `components/ProgressBar.tsx`
4. Extract battery status UI → `components/BatteryCard.tsx`
5. Extract presets UI → `components/PresetSelector.tsx`
6. Extract calibration UI → `components/CalibrationsPanel.tsx`
7. Create `hooks/useAutoRefresh.ts` for data fetching logic
8. Update `index.tsx` to import and compose

## Estimated Effort
- ~4 hours (find/replace imports, debug module resolution)
- ~2 hours (component tests)
- Total: ~6 hours, ~1 week timeline

## Not Doing in v1.0
- CSS modules (inline styles work, premature optimization)
- Component library (shadcn/ui, etc. — adds dependencies)
- Storybook (single developer, not needed yet)

