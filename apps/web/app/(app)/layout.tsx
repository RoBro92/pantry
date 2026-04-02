export default function AppSectionLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <div className="page-shell nested-shell">{children}</div>;
}

