import type { ReactNode } from "react";

export default async function DashboardLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return children;
}
