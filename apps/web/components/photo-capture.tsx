"use client";

import { useMutation } from "@tanstack/react-query";
import { useId, useState } from "react";
import type { Angle, Photo, ScanTicket } from "@proofscan/api-client";
import { Button } from "./ui/button";
import { ErrorNote } from "./shared";
import { EvidenceGallery } from "./evidence-gallery";
import { CameraPicker } from "./camera-picker";

export const views: Angle[] = ["front", "back", "left", "right"];
export const angleName: Record<Angle, string> = { front: "Front", back: "Back", left: "Left side", right: "Right side" };

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

export function PhotoCapture({ path, ticket, photos, onSaved, required }: {
  path: string; ticket: ScanTicket; photos: Photo[]; onSaved: () => void; required?: boolean;
}) {
  return <details open={required || undefined}>
    <summary>Add exterior photos</summary>
    <p>{required ? "Front and back are required. Side views are optional." : "Capture the sides that show the condition."} Keep faces, addresses and serial labels out of frame.</p>
    <AngleCapture savedViews={photos.map(photo => photo.angle)} onSaved={onSaved}
      upload={(angle, image) => fetch("/api/v1" + path + "/photos?angle=" + angle, {
        method: "POST", headers: { "Content-Type": "image/jpeg", "X-Scan-Challenge": ticket.challenge },
        body: image, signal: AbortSignal.timeout(30_000),
      })} />
    <EvidenceGallery items={photos.map(item => ({ href: "/api/v1" + path + "/photos/" + item.id,
      label: "Open " + item.angle + " photo", width: item.width, height: item.height }))} />
  </details>;
}

export function AngleCapture({ savedViews, upload, onSaved }: {
  savedViews: Angle[]; upload: (angle: Angle, image: Blob) => Promise<Response>; onSaved: (angle: Angle) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [selected, setAngle] = useState<Angle | null>(null);
  const angleLabel = useId();
  const next = views.find(view => !savedViews.includes(view));
  const angle = selected ?? next ?? "front";
  const capture = useMutation({
    mutationFn: async ({ photo, view }: { photo: File; view: Angle }) => {
      const image = await jpeg(photo);
      const response = await upload(view, image).catch(() => { throw new Error("Could not upload the photo. Check your connection and try again."); });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : "The photo could not be saved.");
      }
      return view;
    },
    onSuccess: view => { setFile(null); setAngle(null); onSaved(view); },
  });
  return <div className="form">
      <ul className="capture-progress" aria-label="Photo progress">{views.map(view => <li key={view} data-saved={savedViews.includes(view)}>
        {angleName[view]} <span>{savedViews.includes(view) ? "Saved" : view === "front" || view === "back" ? "Pending" : "Optional"}</span>
      </li>)}</ul>
      <label><span id={angleLabel}>Photo angle</span><select aria-labelledby={angleLabel} value={angle} disabled={capture.isPending} onChange={event => { setAngle(event.target.value as Angle); setFile(null); capture.reset(); }}>
        {views.map(view => <option key={view} value={view}>{angleName[view]}</option>)}
      </select></label>
      <CameraPicker key={angle + ":" + savedViews.length} label="Device photo" onPhoto={setFile} disabled={capture.isPending} />
      {file && <p className="muted">{angleName[angle]} photo ready to check.</p>}
      <Button variant="outline" disabled={!file || capture.isPending} onClick={() => { if (file) capture.mutate({ photo: file, view: angle }); }}>
        {capture.isPending ? "Checking photo…" : "Check and save photo"}
      </Button>
      <ErrorNote error={capture.error} />
      {capture.isSuccess && <p role="status">{angleName[capture.data]} photo saved for review.</p>}
  </div>;
}
