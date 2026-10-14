import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MasteryPath",
  description: "以知识地图为中心的掌握式学习工作区",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  );
}
