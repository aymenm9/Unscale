import AiStatusBanner from "@/components/ai-status-banner";
import Nav from "@/components/nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Nav />
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-8">
        <AiStatusBanner />
        {children}
      </main>
    </div>
  );
}
