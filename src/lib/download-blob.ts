export interface ObjectUrlLifecycle {
  createObjectURL(blob: Blob): string;
  revokeObjectURL(url: string): void;
}

const defaultLifecycle: ObjectUrlLifecycle = {
  createObjectURL: (blob) => URL.createObjectURL(blob),
  revokeObjectURL: (url) => URL.revokeObjectURL(url),
};

export function saveVerifiedArtifactBlob(
  blob: Blob,
  filename: string,
  lifecycle: ObjectUrlLifecycle = defaultLifecycle,
): void {
  const objectUrl = lifecycle.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.hidden = true;
  try {
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    lifecycle.revokeObjectURL(objectUrl);
  }
}
