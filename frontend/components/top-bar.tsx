"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useScope } from "@/contexts/ScopeContext";

import { useAuth } from "@/contexts/AuthContext";

const NAV = [
  { href: "/",        label: "Overview" },
  { href: "/explore", label: "Explore"  },
  { href: "/chat",    label: "Chat"     },
];

export function TopBar() {
  const pathname = usePathname();
  const { scopeLabel, scope } = useScope();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b bg-background flex items-center px-6 gap-4 sticky top-0 z-20">
      <nav className="flex items-center gap-1">
        {NAV.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        {scope.projectId && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground border rounded-full px-2.5 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
            <span className="font-medium truncate max-w-[200px]">{scopeLabel}</span>
          </span>
        )}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="w-8 h-8 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-base"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        {user && (
          <div className="flex items-center gap-2 pl-2 border-l">
            <span className="text-xs text-muted-foreground hidden sm:block">{user.name}</span>
            <button
              onClick={logout}
              className="text-xs text-muted-foreground hover:text-foreground hover:bg-muted px-2 py-1 rounded-md transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
