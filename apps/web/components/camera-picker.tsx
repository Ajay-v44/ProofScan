"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";

function liveTip(video: HTMLVideoElement, canvas: HTMLCanvasElement): string | null {
  if (!video.videoWidth || video.readyState < 2) return null;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(video, 0, 0, 96, 72);
  const pixels = context.getImageData(0, 0, 96, 72).data;
  let sum = 0;
  let variation = 0;
  let left = 0;
  for (let offset = 0; offset < pixels.length; offset += 4) {
    const light = 0.299 * pixels[offset] + 0.587 * pixels[offset + 1] + 0.114 * pixels[offset + 2];
    sum += light;
    if (offset % (96 * 4)) variation += Math.abs(light - left);
    left = light;
  }
  const count = pixels.length / 4;
  if (sum / count < 42) return "Add more even light.";
  if (sum / count > 218) return "Reduce glare or move away from direct light.";
  if (variation / count < 3.5) return "Hold steady and make sure the item is in focus.";
  return "Keep the whole side within the frame.";
}

export function CameraPicker({ label, onPhoto, disabled = false }: {
  label: string; onPhoto: (file: File | null) => void; disabled?: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const request = useRef(0);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [starting, setStarting] = useState(false);
  const [tip, setTip] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => () => { request.current++; }, []);
  useEffect(() => {
    if (!stream || !video.current) return;
    video.current.srcObject = stream;
    const sample = document.createElement("canvas");
    sample.width = 96;
    sample.height = 72;
    const clock = window.setInterval(() => {
      if (video.current) setTip(liveTip(video.current, sample));
    }, 500);
    return () => {
      window.clearInterval(clock);
      stream.getTracks().forEach(track => track.stop());
    };
  }, [stream]);

  async function open() {
    const id = ++request.current;
    setStarting(true);
    setError("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      if (id === request.current) setStream(media);
      else media.getTracks().forEach(track => track.stop());
    } catch {
      if (id === request.current) setError("The camera is unavailable. Use the photo picker to continue.");
    } finally {
      if (id === request.current) setStarting(false);
    }
  }

  function capture() {
    const preview = video.current;
    if (!preview?.videoWidth) return;
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 1280 / Math.max(preview.videoWidth, preview.videoHeight));
    canvas.width = Math.round(preview.videoWidth * scale);
    canvas.height = Math.round(preview.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(preview, 0, 0, canvas.width, canvas.height);
    const id = request.current;
    canvas.toBlob(blob => {
      if (id !== request.current) return;
      if (blob) onPhoto(new File([blob], "camera-photo.jpg", { type: "image/jpeg" }));
      else setError("Could not capture this frame. Try again.");
      setStream(null);
      setTip(null);
    }, "image/jpeg", 0.8);
  }

  return <div className="camera-picker">
    <label>{label}<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment"
      disabled={disabled} onChange={event => onPhoto(event.target.files?.[0] ?? null)} /></label>
    {!stream && <Button variant="quiet" disabled={disabled || starting}
      onClick={() => void open()}>{starting ? "Opening camera…" : "Open live camera"}</Button>}
    {stream && <>
      <video ref={video} muted playsInline autoPlay aria-label="Local camera preview" />
      <p role="status">{tip ?? "Waiting for the camera…"}</p>
      <div className="actions">
        <Button variant="outline" onClick={capture} disabled={!tip || disabled}>Capture this view</Button>
        <Button variant="quiet" onClick={() => { request.current++; setStream(null); setTip(null); }}>Close camera</Button>
      </div>
    </>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
