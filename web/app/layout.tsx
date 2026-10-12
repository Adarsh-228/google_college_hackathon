import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Harness Kit • Google Cloud Agent Observability",
  description: "Don't guess your agent's harness. Measure it. Based on arXiv:2609.20804.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas min-h-screen text-heading">{children}</body>
    </html>
  );
}
