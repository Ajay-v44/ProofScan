export const colors = {
  canvas: "#f3f5f7",
  surface: "#ffffff",
  ink: "#142538",
  muted: "#495c6f",
  line: "#dce3ea",
  border: "#a9b7c5",
  brand: "#1c435d",
  brandHover: "#153248",
  brandTint: "#e9f1f6",
  focus: "#1973a0",
  navy: "#101e2c",
  navyRaised: "#1b3044",
  inverseText: "#eaf1f7",
  inverseMuted: "#b4c3d1",
  accent: "#ffae83",
  accentHover: "#ffc5a6",
  mint: "#e6f2ec",
  mintInk: "#20513b",
  cream: "#fff0dc",
  creamInk: "#73411f",
  danger: "#9a2731",
  dangerTint: "#fbe9e9",
} as const;

export const radii = { control: 8, card: 12, cover: 16 } as const;

export const themeVariables = {
  ...Object.fromEntries(Object.entries(colors).map(([name, value]) => [
    "--ps-" + name.replace(/[A-Z]/g, letter => "-" + letter.toLowerCase()), value,
  ])),
  "--ps-control": radii.control + "px",
  "--ps-card": radii.card + "px",
  "--ps-cover": radii.cover + "px",
};
