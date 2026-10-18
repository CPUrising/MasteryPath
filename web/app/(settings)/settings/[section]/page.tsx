import { SettingsPageContent } from "@/components/settings/SettingsPageContent";

export default function SettingsSectionPage({ params }: { params: { section: string } }) {
  return <SettingsPageContent section={params.section} />;
}
