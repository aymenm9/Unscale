import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const archivo = Archivo({ variable: "--font-archivo", subsets: ["latin"], axes: ["wdth"] });

export const metadata: Metadata = {
  title: "Ledgerwise Outreach",
  description: "Run and control the Ledgerwise AI sales assistant.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${archivo.variable} h-full antialiased`}>
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
