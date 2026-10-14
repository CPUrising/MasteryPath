"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { Workspace } from "../components/Workspace";

function WorkspaceRoute() {
  const params = useSearchParams();
  const pathId = params.get("path") ?? "p";
  return <Workspace pathId={pathId} />;
}

export default function Page() {
  return (
    <Suspense fallback={<main style={{ padding: 24 }}>加载中…</main>}>
      <WorkspaceRoute />
    </Suspense>
  );
}
