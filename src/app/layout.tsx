import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./artifacts.css";
import "./globals.css";
import "./playback.css";
import "./progress.css";
import "./review.css";

export const metadata: Metadata = {
  title: "Saxo",
  description: "Create and inspect a saxophone transcription job from an MP3 or WAV file.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
