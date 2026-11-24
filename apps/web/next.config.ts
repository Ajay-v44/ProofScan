import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  transpilePackages: ["@proofscan/api-client", "@proofscan/design-tokens"],
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  poweredByHeader: false,
  devIndicators: false,
  async redirects() {
    return [
      { source: "/", has: [{ type: "query", key: "view", value: "(?:verifications|activity)" }], destination: "/workspace", permanent: true },
      { source: "/", has: [{ type: "query", key: "action", value: "(?:search|seller)" }], destination: "/workspace", permanent: true },
    ];
  },
  async rewrites() {
    const origin = process.env.API_INTERNAL_ORIGIN || "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: origin + "/api/v1/:path*" }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: "base-uri 'none'; form-action 'self'; object-src 'none'; frame-ancestors 'none'" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    }, {
      source: "/:section(workspace|admin|reports|seller|capture|accept|advisor|handoffs)/:path*",
      headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
    }, {
      source: "/verify/:id",
      headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
    }];
  },
};
export default config;
