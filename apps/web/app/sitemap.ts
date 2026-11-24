import type { MetadataRoute } from "next";
import { isPublicSite, siteOrigin } from "../components/marketing/site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  return isPublicSite ? ["/", "/about", "/help", "/privacy", "/verify"].map(path => ({ url: new URL(path, siteOrigin).href })) : [];
}
