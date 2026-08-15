"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/rates", label: "Rates" },
  { href: "/markets", label: "Markets" },
  { href: "/health", label: "Sources" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="hair-b bg-surface/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto max-w-[1180px] px-6 h-12 flex items-center gap-8">
        <Link href="/" className="font-semibold tracking-tight text-[15px]">
          TMD <span className="text-ink-2 font-normal">Markets</span>
        </Link>
        <nav className="flex gap-6 text-[13px]">
          {links.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={active ? "text-ink border-b border-ink -mb-px pb-[13px] pt-[14px]" : "text-ink-2 hover:text-ink pt-[14px] pb-[14px]"}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto text-[12px] text-muted">Sydney time</div>
      </div>
    </header>
  );
}
