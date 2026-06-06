import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "医保审计自查工作台",
  description: "面向医院和机构自查人员的医保审计知识库与自查工作台"
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
