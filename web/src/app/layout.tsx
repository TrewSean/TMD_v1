import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Nav from "@/components/Nav";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "TMD Markets",
  description: "Australian and US rates, equities, FX and commodities. Data from primary publishers and licensed feeds, refreshed automatically.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-AU" className={inter.variable}>
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto max-w-[1180px] px-6 pb-24">{children}</main>
        <footer className="mx-auto max-w-[1180px] px-6 py-8 hair-t text-[12px] text-muted">
          Free end-of-day and delayed public data plus licensed feeds. Not a pricing source. Every figure carries the time it was fetched.
        </footer>
      </body>
    </html>
  );
}
