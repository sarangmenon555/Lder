import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata = {
  title: "Lder",
  description: "Daily Malayalam voice check-ins for elderly parents, with alerts to family anywhere in the world.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Noto+Sans+Malayalam:wght@400;500;600&family=Young+Serif&display=swap"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
