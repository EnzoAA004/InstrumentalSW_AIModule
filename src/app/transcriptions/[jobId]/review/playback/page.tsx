import { TranscriptionSynchronizedPlayback } from "@/components/transcription-synchronized-playback";

interface TranscriptionSynchronizedPlaybackPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function TranscriptionSynchronizedPlaybackPage({
  params,
}: TranscriptionSynchronizedPlaybackPageProps) {
  const { jobId } = await params;
  return (
    <main className="page-shell">
      <TranscriptionSynchronizedPlayback key={jobId} jobId={jobId} />
    </main>
  );
}
