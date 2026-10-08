import type { Metadata } from "next";
import { ResourceViewerView } from "@/components/student/my-courses/resource-viewer-view";

export const metadata: Metadata = { title: "Document Viewer" };

interface ViewerPageProps {
  params: Promise<{ id: string; resourceId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function ResourceViewerPage({ params, searchParams }: ViewerPageProps) {
  const [{ id, resourceId }, query] = await Promise.all([params, searchParams]);
  const raw = Array.isArray(query.page) ? query.page[0] : query.page;
  const parsed = Number.parseInt(raw ?? "", 10);
  const initialPage = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  return <ResourceViewerView courseId={id} resourceId={resourceId} initialPage={initialPage} />;
}
