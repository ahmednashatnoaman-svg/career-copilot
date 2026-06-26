"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Upload,
  MessageSquare,
  Search,
  GraduationCap,
  ClipboardList,
  Briefcase,
  Mic,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  {
    href: "/onboarding",
    label: "Onboarding",
    description: "Upload resume & profile",
    icon: Upload,
  },
  {
    href: "/copilot",
    label: "Copilot",
    description: "AI career assistant",
    icon: MessageSquare,
  },
  {
    href: "/matches",
    label: "Matches",
    description: "Job recommendations",
    icon: Search,
  },
  {
    href: "/coaching",
    label: "Coaching",
    description: "Interview & skill tips",
    icon: GraduationCap,
  },
  {
    href: "/applications",
    label: "Applications",
    description: "Track applications",
    icon: ClipboardList,
  },
  {
    href: "/interviews",
    label: "Interviews",
    description: "Mock interview practice",
    icon: Mic,
  },
  {
    href: "/admin",
    label: "Admin",
    description: "System stats & memory",
    icon: ShieldCheck,
  },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col h-full">
      {/* Logo / Brand */}
      <div className="flex items-center gap-2.5 px-4 py-5 border-b border-sidebar-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
          <Briefcase className="h-4 w-4 text-sidebar-primary-foreground" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-sidebar-foreground leading-tight">
            Career Copilot
          </span>
          <span className="text-xs text-sidebar-foreground/50 leading-tight">
            AI-powered job search
          </span>
        </div>
      </div>

      {/* Nav links */}
      <div className="flex-1 px-2 py-4 space-y-0.5">
        <p className="px-2 pb-2 text-xs font-medium uppercase tracking-wider text-sidebar-foreground/40">
          Navigation
        </p>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  isActive
                    ? "text-sidebar-primary-foreground"
                    : "text-sidebar-foreground/50 group-hover:text-sidebar-accent-foreground"
                )}
              />
              <div className="flex flex-col min-w-0">
                <span className="font-medium leading-tight">{item.label}</span>
                <span
                  className={cn(
                    "text-xs leading-tight truncate",
                    isActive
                      ? "text-sidebar-primary-foreground/70"
                      : "text-sidebar-foreground/40 group-hover:text-sidebar-accent-foreground/60"
                  )}
                >
                  {item.description}
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-sidebar-border">
        <p className="text-xs text-sidebar-foreground/30 text-center">
          v0.1.0 &middot; beta
        </p>
      </div>
    </nav>
  );
}
