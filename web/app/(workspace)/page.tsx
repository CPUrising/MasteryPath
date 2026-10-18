import { redirect } from "next/navigation";

import { MASTERY_HOME } from "@/lib/learning-routes";

export default function WorkspaceHome() {
  redirect(MASTERY_HOME);
}
