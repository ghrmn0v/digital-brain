import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // One product identity across the three subsystems: the Core Brain is the
  // intelligence, Fly the behaviour engine, and this app is the surface the
  // person actually uses. The page title carries the product, not the layer.
  title: {
    default: "Digital Brain",
    template: "%s · Digital Brain",
  },
  description:
    "Your local-first digital brain: it remembers what your life is about, learns how you prefer to work, and proposes what to do next. Tasks, calendar, jobs, approvals and automations, backed by Core Brain memory and Fly behaviour.",
  applicationName: "Digital Brain",
  keywords: [
    "digital brain",
    "personal AI",
    "local-first",
    "memory",
    "calendar",
    "tasks",
    "automations",
  ],
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#020617",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
