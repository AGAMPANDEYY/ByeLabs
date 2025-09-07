import "./globals.css";
import type { Metadata } from "next";
import { AppNavbar } from "@/components/app-navbar";

export const metadata: Metadata = {
  title: "HiLabs Roster Automation",
  description: "Local, multi-agent roster extraction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased">
        <AppNavbar />
        {children}
      </body>
    </html>
  );
}