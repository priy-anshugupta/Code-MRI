import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import ErrorBoundary from "@/components/ErrorBoundary";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

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
                inter.variable,
                jetbrainsMono.variable
            )}>
                <ErrorBoundary level="page">
                    {children}
                </ErrorBoundary>
            </body>
        </html>
    );
}
