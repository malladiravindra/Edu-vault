/**
 * Settings API — real backend endpoints.
 *
 *   GET   /api/admin/settings/          → all settings
 *   PATCH /api/admin/settings/          → update settings (partial)
 *
 * Note: The backend uses a single PATCH endpoint for the whole settings object,
 * not a per-section PUT. The section parameter is kept in the interface for
 * backwards compatibility with existing hook callers.
 */
import type { AdminSettings } from "@/types";
import { http } from "./client";

export type SettingsSection = keyof AdminSettings;

export interface SettingsApi {
  get(): Promise<AdminSettings>;
  update<K extends SettingsSection>(section: K, values: AdminSettings[K]): Promise<AdminSettings>;
}

export const settingsApi: SettingsApi = {
  get: () => http.get("/admin/settings/"),
  // Send the section's values wrapped in the section key so the backend knows
  // which sub-object to update (e.g. { platform: { ... } }).
  update: (section, values) => http.patch("/admin/settings/", { [section]: values }),
};
