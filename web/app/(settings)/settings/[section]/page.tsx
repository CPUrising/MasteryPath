import { SettingsPageContent } from "@/components/settings/SettingsPageContent";

export default function SettingsSectionPage({ params }: { params: { section: string } }) {
  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-7">
      <SettingsPageContent section={params.section} />
    </div>
  );
}
