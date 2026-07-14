import { Link } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";

const NotFound = () => {
  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main flex min-h-[70vh] items-center justify-center">
        <div className="glass-panel max-w-md rounded-[2rem] p-8 text-center">
          <p className="eyebrow mb-3">404</p>
          <h1 className="mb-3 text-4xl font-black tracking-tight">Page not found</h1>
          <p className="mb-6 text-muted-foreground">This route is not part of your career workspace.</p>
          <Link to="/">
            <Button className="rounded-2xl">Return home</Button>
          </Link>
        </div>
      </main>
    </div>
  );
};

export default NotFound;
