"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

export function Dialog({ title, description, children, onClose, placement = "center" }: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  placement?: "center" | "side" | "workflow";
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

  return <dialog ref={ref} aria-labelledby={titleId} aria-describedby={description ? `${titleId}-description` : undefined} className={"dialog dialog-" + placement}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dialog-frame">
      <header className="dialog-head"><div><h2 id={titleId}>{title}</h2>
        {description && <p id={`${titleId}-description`}>{description}</p>}</div>
        <button className="icon-button" aria-label="Close dialog" type="button" onClick={onClose}><X size={20} aria-hidden /></button>
      </header>
      <div className="dialog-content">{children}</div>
    </div>
  </dialog>;
}
