import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI智能审计管理系统",
  description: "面向医院内审人员的 AI 审计门户、知识库、数据分析和底稿报告工作区"
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
