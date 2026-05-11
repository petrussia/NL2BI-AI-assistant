import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NL2BI AI Assistant",
  description: "Server + Colab NL2BI MVP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

