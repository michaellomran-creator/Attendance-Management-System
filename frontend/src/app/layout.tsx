import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "NORAM Attendance | Multi-Organization Workforce Platform",
  description:
    "Enterprise multi-organization workforce attendance, shift, and compliance management by NORAM DIGITAL SOLUTIONS.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen antialiased bg-[#F4F1EA] text-[#132425]">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
