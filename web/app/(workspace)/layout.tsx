import AppShell from "@/components/layout/AppShell";
import { WorkspaceSidebar } from "@/components/sidebar/WorkspaceSidebar";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <AppShell sidebar={<WorkspaceSidebar />}>{children}</AppShell>;
}
