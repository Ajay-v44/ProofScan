export const colors = {
  canvas: "#f7f7fa",
  surface: "#ffffff",
  ink: "#221d30",
  muted: "#605a70",
  line: "#e5e1ed",
  border: "#d6cfe3",
  brand: "#5131bb",
  brandHover: "#41269c",
  brandTint: "#efeafb",
  focus: "#7854e4",
  lilac: "#eee9f8",
  mint: "#e6f1ea",
  mintInk: "#285645",
  cream: "#fbf0dd",
  creamInk: "#775022",
  danger: "#9c333b",
  dangerTint: "#f9e9eb",
} as const;

export const radii = { control: 9, card: 15, cover: 20 } as const;

export const themeVariables = {
  ...Object.fromEntries(Object.entries(colors).map(([name, value]) => [
    "--ps-" + name.replace(/[A-Z]/g, letter => "-" + letter.toLowerCase()), value,
  ])),
  "--ps-control": radii.control + "px",
  "--ps-card": radii.card + "px",
  "--ps-cover": radii.cover + "px",
};
