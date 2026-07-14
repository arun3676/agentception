import { Link } from "react-router-dom";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";

interface FeatureUnavailableProps {
  feature: string;
}

const FeatureUnavailable = ({ feature }: FeatureUnavailableProps) => (
  <div className="min-h-screen bg-background">
    <TopNav />
    <main className="app-main flex min-h-[70vh] items-center justify-center">
      <section className="card-clean max-w-xl p-7 text-center sm:p-10" role="status" aria-labelledby="feature-unavailable-title">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-muted-foreground">
          <LockKeyhole className="h-6 w-6" aria-hidden="true" />
        </span>
        <p className="section-label mt-5">Private feature unavailable</p>
        <h1 id="feature-unavailable-title" className="mt-2 text-3xl font-black tracking-[-0.04em]">
          {feature} is temporarily unavailable.
        </h1>
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          This feature handles personal data. It will return after authentication, private ownership, retention, and deletion controls are verified.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <Button asChild>
            <Link to="/">
              Search public roles <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/dashboard">View feature status</Link>
          </Button>
        </div>
      </section>
    </main>
  </div>
);

export default FeatureUnavailable;
