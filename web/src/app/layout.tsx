import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppNavbar } from "@/components/app-navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "HiLabs Roster Automation",
  description: "Touchless end-to-end roster processing with AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50">
          <AppNavbar />
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}