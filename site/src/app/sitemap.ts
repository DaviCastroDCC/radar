import type { MetadataRoute } from "next";

import { site } from "@/config/site";
import { buscarEditais } from "@/lib/api";
import { urlEdital } from "@/lib/formato";

/** Mapa do site para o Google: páginas fixas + os editais mais recentes. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const editais = await buscarEditais({ limite: 100 });
  return [
    { url: site.url, changeFrequency: "hourly", priority: 1 },
    { url: `${site.url}/concursos`, changeFrequency: "hourly", priority: 0.9 },
    ...editais.map((e) => ({
      url: `${site.url}${urlEdital(e)}`,
      lastModified: e.data_publicacao,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
  ];
}
