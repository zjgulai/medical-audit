import type { Metadata } from "next";

import { AUDIT_PLATFORM_DESCRIPTION, AUDIT_PLATFORM_NAME } from "@/lib/brand";

import "./globals.css";

export const metadata: Metadata = {
  title: AUDIT_PLATFORM_NAME,
  description: AUDIT_PLATFORM_DESCRIPTION
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
