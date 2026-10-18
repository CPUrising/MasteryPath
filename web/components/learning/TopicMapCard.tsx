"use client";

import Link from "next/link";

import { masteryTopicRoute } from "@/lib/learning-routes";

export interface TopicCardData {
  path_id: string;
  name: string;
  goal: string;
  objectives: number;
}

export function TopicMapCard({ topic }: { topic: TopicCardData }) {
  return (
    <Link
      href={masteryTopicRoute(topic.path_id)}
      className="block rounded-xl border border-border bg-card p-5 transition hover:-translate-y-0.5 hover:border-primary/35"
    >
      <h3 className="text-[15px] font-semibold">{topic.name || topic.path_id}</h3>
      <p className="mt-1 line-clamp-2 text-[13px] text-muted-foreground">
        {topic.goal || "—"}
      </p>
      <div className="mt-4 text-[12px] text-muted-foreground">
        {topic.objectives} KP
      </div>
    </Link>
  );
}
