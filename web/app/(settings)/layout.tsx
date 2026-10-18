import AppShell from "@/components/layout/AppShell";
import { SettingsNav } from "@/components/settings/SettingsNav";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <AppShell sidebar={<SettingsNav />}>{children}</AppShell>;
}
