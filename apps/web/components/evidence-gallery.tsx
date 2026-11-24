"use client";

import { ImageIcon } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { Dialog } from "./ui/dialog";

type Evidence = { href: string; label: string; width?: number; height?: number };

function EvidenceImage({ item, thumbnail }: { item: Evidence; thumbnail?: boolean }) {
  const [failed, setFailed] = useState(false);
  return failed
    ? <p className="notice warning" role="status">This photo is unavailable or has expired.</p>
    : <Image className="evidence-image" src={item.href} alt={thumbnail ? "" : item.label}
        unoptimized width={item.width ?? 1200} height={item.height ?? 800} onError={() => setFailed(true)} />;
}

export function EvidenceGallery({ items, thumbnails = false }: { items: Evidence[]; thumbnails?: boolean }) {
  const [selected, setSelected] = useState<Evidence | null>(null);
  if (!items.length) return null;
  return <>
    <div className={thumbnails ? "evidence-grid" : "evidence-links"}>{items.map(item => <a className="evidence-link" href={item.href} key={item.href} aria-label={item.label}
      onClick={event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        setSelected(item);
      }}>{thumbnails ? <EvidenceImage item={item} thumbnail /> : <ImageIcon size={16} aria-hidden />}<span>{item.label}</span></a>)}</div>
    {selected && <Dialog title={selected.label} onClose={() => setSelected(null)}>
      <EvidenceImage item={selected} key={selected.href} />
    </Dialog>}
  </>;
}
