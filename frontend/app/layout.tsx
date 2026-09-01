import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { AppBackground } from "@/components/ui/AppBackground";
import { getSession } from "@/lib/session";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Terra Audit",
  description: "Carbon credit MRV dashboard — VM0051 rice AWD & VM0042 cropland ALM",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const session = await getSession();
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col bg-background text-foreground">
        <Script
          id="extension-hydration-cleanup"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (() => {
                const removeInjectedAttrs = () => {
                  document.querySelectorAll("*").forEach((el) => {
                    for (const attr of [...el.attributes]) {
                      if (
                        attr.name === "bis_skin_checked" ||
                        attr.name === "bis_register" ||
                        attr.name.startsWith("__processed_")
                      ) {
                        el.removeAttribute(attr.name);
                      }
                    }
                  });
                };
                removeInjectedAttrs();
                const observer = new MutationObserver(removeInjectedAttrs);
                observer.observe(document.documentElement, {
                  attributes: true,
                  childList: true,
                  subtree: true,
                });
                window.addEventListener("load", () => {
                  removeInjectedAttrs();
                  window.setTimeout(() => observer.disconnect(), 1500);
                });
              })();
            `,
          }}
        />
        <AppBackground />
        <Providers session={session}>{children}</Providers>
      </body>
    </html>
  );
}
