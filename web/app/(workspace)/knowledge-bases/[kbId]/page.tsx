import { KnowledgeBaseDetail } from "@/components/knowledge/KnowledgeBaseDetail";

export default function KnowledgeBasePage({
  params,
}: {
  params: { kbId: string };
}) {
  return <KnowledgeBaseDetail kbId={decodeURIComponent(params.kbId)} />;
}
