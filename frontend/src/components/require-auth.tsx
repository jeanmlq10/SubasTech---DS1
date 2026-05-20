"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { restoreSession } from "@/lib/auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;

    void (async () => {
      const session = await restoreSession();
      if (!mounted) {
        return;
      }
      if (!session) {
        router.replace("/login");
        return;
      }
      setReady(true);
    })();

    return () => {
      mounted = false;
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <Loader2 className="size-8 animate-spin text-emerald-600" />
      </div>
    );
  }

  return <>{children}</>;
}
