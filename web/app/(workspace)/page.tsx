import { redirect } from "next/navigation";

import { CHAT_HOME } from "@/lib/learning-routes";

export default function WorkspaceHome() {
  redirect(CHAT_HOME);
}
