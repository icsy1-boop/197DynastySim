import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DynastySim",
  description: "Barangay Mabuhay — Political Dynasty Simulation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="bg-gray-950 text-white h-full flex flex-col antialiased">
        <nav className="bg-gray-900 border-b border-gray-700 px-4 py-2 flex items-center gap-6 shrink-0">
          <span className="font-bold text-yellow-400 tracking-wider text-sm">DYNASTYSIM</span>
          <a href="/replay"        className="text-xs text-gray-400 hover:text-white transition-colors">World Replay</a>
          <a href="/conversations" className="text-xs text-gray-400 hover:text-white transition-colors">Conversations</a>
          <a href="/compare"       className="text-xs text-gray-400 hover:text-white transition-colors">Compare</a>
        </nav>
        <main className="flex-1 flex flex-col overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
