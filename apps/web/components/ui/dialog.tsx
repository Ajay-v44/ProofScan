"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

export function Dialog({ title, children, onClose, placement = "center" }: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  placement?: "center" | "side";
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>("[data-dialog-autofocus]")?.focus();
    return () => {
      dialog?.close();
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, []);

  return <dialog ref={ref} aria-labelledby={titleId} className={"dialog dialog-" + placement}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dialog-frame">
      <header className="dialog-head"><h2 id={titleId}>{title}</h2>
        <button className="icon-button" aria-label="Close dialog" type="button" onClick={onClose}><X size={20} aria-hidden /></button>
      </header>
      <div className="dialog-content">{children}</div>
    </div>
  </dialog>;
}
