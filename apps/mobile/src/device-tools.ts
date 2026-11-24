import type { DeviceTool, Hardware, ToolOutcome } from "@proofscan/api-client";
import * as Device from "expo-device";

export type MobileReadings = Pick<Hardware, "manufacturer" | "model" | "memory_gib">;

const text = (value: string | null) => value?.trim().slice(0, 120) || null;

const readers: Record<DeviceTool, () => MobileReadings> = {
  model_name: () => ({
    manufacturer: text(Device.manufacturer),
    model: text(Device.modelName),
  }),
  model_identifier: () => ({
    manufacturer: text(Device.manufacturer) ?? text(Device.brand),
    model: text(Device.modelId) ?? text(Device.productName) ?? text(Device.designName),
  }),
  memory_total: () => ({
    memory_gib: Device.totalMemory ? Math.max(1, Math.round(Device.totalMemory / 2 ** 30)) : null,
  }),
};

export function runDeviceTool(tool: DeviceTool): { outcome: ToolOutcome; readings: MobileReadings } {
  if (!Object.hasOwn(readers, tool)) throw new Error("This build does not support that device check.");
  try {
    const readings = readers[tool]();
    return { outcome: readings.model || readings.memory_gib ? "ok" : "unavailable", readings };
  } catch {
    return { outcome: "error", readings: {} };
  }
}
