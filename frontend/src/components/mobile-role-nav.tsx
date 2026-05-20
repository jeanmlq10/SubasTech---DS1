"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LogIn, Scale, ShieldCheck, Wrench } from "lucide-react";

const links = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/technician/dashboard", label: "Tecnico", icon: Wrench },
  { href: "/admin", label: "Admin", icon: ShieldCheck },
  { href: "/arbiter", label: "Arbitro", icon: Scale },
  { href: "/login", label: "Login", icon: LogIn },
];

export function MobileRoleNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-3 bottom-3 z-50 rounded-3xl border bg-background/95 p-2 shadow-2xl backdrop-blur md:hidden">
      <div className="grid grid-cols-5 gap-1">
        {links.map((link) => {
          const Icon = link.icon;
          const active = pathname === link.href || (link.href === "/technician/dashboard" && pathname.startsWith("/technician"));
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-medium transition-colors ${
                active ? "bg-emerald-600 text-white" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="size-4" />
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
