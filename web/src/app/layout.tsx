import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI审计应用",
  description: "面向审计人员的 AI 对话、智能体、知识库、文档检索、数据分析和底稿工作区",
  icons: {
    icon: "/ai-replica-icon.svg"
  }
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
