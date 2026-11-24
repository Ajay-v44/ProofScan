import type { MetadataRoute } from "next";
import { isPublicSite, siteOrigin } from "../components/marketing/site-config";

export default function robots(): MetadataRoute.Robots {
  return isPublicSite
    ? { rules: { userAgent: "*", allow: "/", disallow: "/api/" }, sitemap: new URL("/sitemap.xml", siteOrigin).href }
    : { rules: { userAgent: "*", disallow: "/" } };
}
