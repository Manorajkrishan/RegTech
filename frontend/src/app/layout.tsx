import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ESG RegTech Platform | SME Compliance",
  description: "AI-powered ESG data collection and reporting for SMEs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}
