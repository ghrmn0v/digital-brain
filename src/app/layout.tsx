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
    default: "Cerebro Flow",
    template: "%s · Cerebro Flow",
  },
  description:
    "Your local-first digital brain: it remembers what your life is about, learns how you prefer to work, and proposes what to do next. Tasks, calendar, jobs, approvals and automations, backed by Core Brain memory and Fly behaviour.",
  applicationName: "Cerebro Flow",
  keywords: [
    "cerebro flow",
    "personal AI",
    "local-first",
    "memory",
    "calendar",
    "tasks",
    "automations",
  ],
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0e12" },
  ],
};

/**
 * Applied before first paint, in the document itself.
 *
 * The server has no access to localStorage, so it renders `data-theme="light"`
 * on <html>. Without this the saved choice would only take effect after a
 * reload, flashing the wrong theme and repainting the whole app. Running it
 * synchronously in <head> means the attribute is already correct when the
 * first pixel lands. It mutates the DOM React owns, but only the attribute it
 * set in the first place, and it stays in agreement with `getServerTheme`.
 */
const THEME_BOOTSTRAP = `try{var t=localStorage.getItem("product.theme");document.documentElement.setAttribute("data-theme",t==="dark"?"dark":"light")}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // Light is the default surface; the bootstrap below may override it.
      data-theme="light"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
