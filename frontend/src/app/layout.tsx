import type { Metadata } from "next";
import { Inter } from "next/font/google"; // Using Inter as requested for modern look
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
    title: "Code MRI - Autonomous Audit",
    description: "Secure Static Analysis & Intelligence Engine",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" className="dark">
            <body className={cn(
                "min-h-screen bg-background font-sans antialiased",
                inter.variable
            )}>
                {children}
            </body>
        </html>
    );
}
