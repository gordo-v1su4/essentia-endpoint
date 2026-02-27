import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Essentia Next.js Proxy",
  description: "Next.js proxy for Essentia audio analysis API"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
