import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "医保智能审计平台",
  description: "面向医院内审人员的医保基金审计、依据检索、表格分析和底稿工作区"
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
