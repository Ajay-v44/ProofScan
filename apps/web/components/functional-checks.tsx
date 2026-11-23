"use client";

import type { FunctionalCheck } from "@proofscan/api-client";
import { useState } from "react";
import { Button } from "./ui/button";

export const checkLabels = { display: "Display", keyboard: "Keyboard", speakers: "Speakers" };

async function playSample() {
  const context = new AudioContext();
  try {
    await context.resume();
    const tone = context.createOscillator();
    const volume = context.createGain();
    volume.gain.setValueAtTime(0.065, context.currentTime);
    tone.frequency.value = 440;
    tone.connect(volume).connect(context.destination);
    tone.onended = () => { void context.close(); };
    tone.start();
    tone.stop(context.currentTime + 0.55);
  } catch (error) {
    await context.close();
    throw error;
  }
}

export function FunctionalChecks({ checks, onChange }: {
  checks: FunctionalCheck[];
  onChange: (next: FunctionalCheck[]) => void;
}) {
  const [soundError, setSoundError] = useState("");
  return <details>
    <summary>Check the display, keyboard and speakers</summary>
    <div className="form">
      <p>Run each check on the device being sold and record what you observe. You can skip any check.</p>
      <div aria-label="Display color test" role="img" style={{ display: "flex", height: 52, border: "1px solid #8b9f94", borderRadius: 8, overflow: "hidden" }}>
        {["#152020", "#fff", "#c9514c", "#428256", "#2d68ad"].map(color => <span key={color} style={{ background: color, flex: 1 }} />)}
      </div>
      <label>Keyboard test area<input autoComplete="off" placeholder="Type a few keys here" /></label>
      <Button variant="outline" onClick={() => {
        setSoundError("");
        void playSample().catch(() => setSoundError("Could not play the sample tone."));
      }}>Play speaker test tone</Button>
      {soundError && <p role="alert">{soundError}</p>}
      <div className="input-grid">{Object.entries(checkLabels).map(([key, label]) => {
        const test = key as FunctionalCheck["test"];
        return <label key={test}>{label} result<select value={checks.find(check => check.test === test)?.result ?? ""} onChange={event => {
          const next = checks.filter(check => check.test !== test);
          const result = event.target.value;
          if (result === "PASS" || result === "ISSUE") next.push({ test, result });
          onChange(next);
        }}>
          <option value="">Skip</option><option value="PASS">Passed</option><option value="ISSUE">Issue observed</option>
        </select></label>;
      })}</div>
    </div>
  </details>;
}
