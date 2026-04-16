import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pantro",
  description: "Self-hosted-first household inventory foundation"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
