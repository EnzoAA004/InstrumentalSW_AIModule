import { TranscriptionRevisionEditor } from "@/components/transcription-revision-editor";

interface TranscriptionRevisionEditorPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function TranscriptionRevisionEditorPage({
  params,
}: TranscriptionRevisionEditorPageProps) {
  const { jobId } = await params;
  return (
    <main className="page-shell">
      <TranscriptionRevisionEditor key={jobId} jobId={jobId} />
    </main>
  );
}
