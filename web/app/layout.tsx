import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Research — Multi-agent",
  description: "Run planner → research → executor → critic against the capstone API",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
