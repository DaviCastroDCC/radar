import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Cabecalho } from "@/components/Cabecalho";
import { Rodape } from "@/components/Rodape";
import { site } from "@/config/site";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: `${site.nome}: concursos públicos com inscrições abertas`, template: `%s | ${site.nome}` },
  description: site.descricao,
  openGraph: { siteName: site.nome, locale: "pt_BR", type: "website" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <Cabecalho />
        <main className="flex-1">{children}</main>
        <Rodape />
      </body>
    </html>
  );
}
