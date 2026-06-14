/**
 * Preset Selector Component
 * 
 * Allows users to quickly apply preconfigured charge limits:
 * - Built-in: Storage (60%), Normal (80%), Full (100%), Travel (95%)
 * - Custom: User-defined presets
 * 
 * Props:
 * - presets: {built_in: {name: percent}, custom: {name: percent}}
 * - onApply: callback(preset_name) -> fires when user selects a preset
 */

import { DropdownItem } from "@decky/ui";

interface PresetSelectorProps {
  presets: {
    built_in: Record<string, number>;
    custom: Record<string, number>;
  };
  onApply: (presetName: string) => void;
}

export function PresetSelector({ presets, onApply }: PresetSelectorProps) {
  // Combine built-in and custom presets into dropdown options
  const presetOptions = [
    ...Object.entries(presets?.built_in ?? {}).map(([name, val]) => ({
      label: `${name} (${val}%)`,
      data: name,
    })),
    ...Object.entries(presets?.custom ?? {}).map(([name, val]) => ({
      label: `${name} (${val}%) [Custom]`,
      data: name,
    })),
  ];

  if (presetOptions.length === 0) {
    return null;
  }

  return (
    <DropdownItem
      label="Presets"
      description="Apply a charge limit preset"
      rgOptions={presetOptions}
      selectedOption={undefined}
      onChange={(opt: { data: string }) => onApply(opt.data)}
    />
  );
}
