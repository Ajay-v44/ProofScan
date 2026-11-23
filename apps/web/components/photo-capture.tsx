"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { Angle, Photo, ScanTicket } from "@proofscan/api-client";
import { Button } from "./ui/button";
import { ErrorNote } from "./shared";
import { EvidenceGallery } from "./evidence-gallery";

export async function jpeg(file: File) {
  if (file.size > 12_000_000) throw new Error("Choose a photo under 12 MB.");
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(image => image ? resolve(image) : reject(new Error("Could not prepare this photo.")), "image/jpeg", 0.77);
    });
  } finally {
    bitmap.close();
  }
}

export function PhotoCapture({ path, ticket, photos, onSaved }: {
  path: string; ticket: ScanTicket; photos: Photo[]; onSaved: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [angle, setAngle] = useState<Angle>("front");
  const capture = useMutation({
    mutationFn: async (photo: File) => {
      const response = await fetch("/api/v1" + path + "/photos?angle=" + angle, {
        method: "POST",
        headers: { "Content-Type": "image/jpeg", "X-Scan-Challenge": ticket.challenge },
        body: await jpeg(photo),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "The photo could not be saved.");
      }
    },
    onSuccess: onSaved,
  });
  return <details>
    <summary>Add exterior photos</summary>
    <p>Photograph the device in even light. Include the entire side and keep any personal details out of frame. A fresh ticket clears the photos attached to the old ticket.</p>
    <div className="form">
      <label>View<select value={angle} onChange={event => setAngle(event.target.value as Angle)}>
        <option value="front">Front</option><option value="back">Back</option><option value="left">Left side</option><option value="right">Right side</option>
      </select></label>
      <label>Device photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
      <Button variant="outline" disabled={!file || capture.isPending} onClick={() => { if (file) capture.mutate(file); }}>
        {capture.isPending ? "Checking photo…" : "Check and save photo"}
      </Button>
      <ErrorNote error={capture.error} />
      {capture.isSuccess && <p role="status">Photo saved for review.</p>}
      <EvidenceGallery items={photos?.map(item => ({ href: "/api/v1" + path + "/photos/" + item.id,
        label: "Open " + item.angle + " photo", width: item.width, height: item.height })) ?? []} />
    </div>
  </details>;
}
