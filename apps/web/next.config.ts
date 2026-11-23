import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  transpilePackages: ["@proofscan/api-client", "@proofscan/design-tokens"],
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  poweredByHeader: false,
  devIndicators: false,
  async rewrites() {
    const origin = process.env.API_INTERNAL_ORIGIN || "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: origin + "/api/v1/:path*" }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    }];
  },
};
export default config;
