import { TranscriptionProgress } from "@/components/transcription-progress";

interface TranscriptionPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function TranscriptionPage({ params }: TranscriptionPageProps) {
  const { jobId } = await params;

  return (
    <main className="page-shell">
      <TranscriptionProgress key={jobId} jobId={jobId} />
    </main>
  );
}
