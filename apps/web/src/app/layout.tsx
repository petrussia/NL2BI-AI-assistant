import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NL2BI — Natural Language Business Intelligence",
  description:
    "Open-source diploma project: ask a business question in natural language, get a SQL-grounded answer with a chart, powered by a Qwen2.5-Coder model on Colab GPU.",
  applicationName: "NL2BI AI Assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
