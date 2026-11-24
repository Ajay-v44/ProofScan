"use client";

import type { CaptureProgress } from "@proofscan/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { AngleCapture } from "./photo-capture";
import { ErrorNote, PublicShell } from "./shared";
import { Button } from "./ui/button";

export function CompanionCapture({ id }: { id: string }) {
  const token = useRef("");
  const client = useQueryClient();
  const key = ["camera-capture", id] as const;
  const path = "/api/v1/capture/" + id;
  const progress = useQuery({
    queryKey: key,
    staleTime: 0,
    gcTime: 0,
    queryFn: async (): Promise<CaptureProgress> => {
      token.current = window.location.hash.slice(1) || token.current;
      if (!/^[A-Za-z0-9_-]{43}$/.test(token.current)) throw new Error("Open the original camera link.");
      const response = await fetch(path, { cache: "no-store", credentials: "omit", redirect: "error",
        signal: AbortSignal.timeout(10_000), headers: { "X-Photo-Token": token.current } });
      if (response.status === 404) throw new Error("This camera link is unavailable. Ask for a fresh link.");
      if (!response.ok) throw new Error("Could not open the camera link. Try again.");
      window.history.replaceState(null, "", window.location.pathname);
      return response.json();
    },
  });
  const savedViews = progress.data?.views ?? [];
  const complete = savedViews.includes("front") && savedViews.includes("back");

  return <PublicShell isGuest>
    <div className="page-title"><h1>Photograph the device</h1><p>Use this camera to take pictures of the device being checked.</p></div>
    <section className="panel form">
      {progress.isPending && <p role="status">Opening camera link…</p>}
      <ErrorNote error={progress.error} />
      {progress.isError && <Button variant="outline" onClick={() => void progress.refetch()}>Try again</Button>}
      {!progress.isError && progress.data && <>
        <h2>Exterior photos</h2>
        {complete ? <p className="notice good" role="status">Front and back saved. Return to the original scanner and select Refresh photos.</p>
          : <p>Take separate front and back photos. Keep faces, addresses and serial labels out of frame.</p>}
        <AngleCapture savedViews={savedViews} upload={(angle, image) => fetch(path + "/photos?angle=" + angle, {
          method: "POST", credentials: "omit", redirect: "error", signal: AbortSignal.timeout(30_000),
          headers: { "Content-Type": "image/jpeg", "X-Photo-Token": token.current }, body: image,
        })} onSaved={angle => client.setQueryData<CaptureProgress>(key, current => ({
          views: [...new Set([...(current?.views ?? []), angle])],
        }))} />
      </>}
    </section>
  </PublicShell>;
}
