import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ProofScan", short_name: "ProofScan", description: "Used device verification and condition reports",
    start_url: "/", scope: "/", display: "browser", background_color: "#f3f5f7", theme_color: "#101e2c", lang: "en",
    icons: [192, 512].map(size => ({ src: "/brand/icon-" + size + ".png", sizes: size + "x" + size, type: "image/png" })),
  };
}
