"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import { CreateTopicWizard, type CreateTopicInput } from "@/components/learning/CreateTopicWizard";
import { TopicAtlas } from "@/components/learning/TopicAtlas";
import { api } from "@/lib/api";
import { masterySessionRoute } from "@/lib/learning-routes";

export default function MasteryAtlasPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [topics, setTopics] = useState<{ path_id: string; name: string; goal: string; objectives: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wizard, setWizard] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setTopics(await api.listPaths());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.retry"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async ({ name, goal, knowledgeBaseIds }: CreateTopicInput) => {
    const pathId = `p${Date.now().toString(36)}`;
    await api.createPath(pathId, goal, name, knowledgeBaseIds);
    setWizard(false);
    router.push(masterySessionRoute(pathId, "outline"));
  };

  return (
    <>
      <TopicAtlas topics={topics} loading={loading} error={error} onCreate={() => setWizard(true)} onRetry={load} />
      <CreateTopicWizard open={wizard} onClose={() => setWizard(false)} onCreate={create} />
    </>
  );
}
