import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tickets.md",
  description:
    "An open-source, in-repo ticketing system for parallel agentic work and human collaboration—offline-first, merge-friendly, and simple by design."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
