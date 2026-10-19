import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

export default function ChatSessionPage({
  params,
}: {
  params: { sessionId: string };
}) {
  return <ChatWorkspace sessionId={decodeURIComponent(params.sessionId)} />;
}
