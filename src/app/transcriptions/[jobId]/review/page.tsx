import { TranscriptionReviewView } from "@/components/transcription-review";

interface TranscriptionReviewPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function TranscriptionReviewPage({ params }: TranscriptionReviewPageProps) {
  const { jobId } = await params;
  return (
    <main className="page-shell">
      <TranscriptionReviewView key={jobId} jobId={jobId} />
    </main>
  );
}
