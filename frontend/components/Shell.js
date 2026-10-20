"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import AuthGate from "@/components/AuthGate";
import { useTz } from "@/components/Providers";
import { clearToken } from "@/lib/api";
import { ZONES } from "@/lib/time";

export default function Shell({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const { tz, setTz } = useTz();
  const zones = ZONES.includes(tz) ? ZONES : [tz, ...ZONES];

  const signOut = () => {
    clearToken();
    router.replace("/login");
  };

  const onDashboard = pathname === "/" || (pathname.startsWith("/elders/") && !pathname.startsWith("/elders/new"));
  const onAdd = pathname.startsWith("/elders/new");

  return (
    <AuthGate>
      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/" className="brand">
            <span className="brand-name">Lder</span>
            <span className="brand-sub">Daily check-ins for family far away</span>
          </Link>
          <nav className="nav" aria-label="Main">
            <Link href="/" className={onDashboard ? "active" : ""}>
              Dashboard
            </Link>
            <Link href="/elders/new" className={onAdd ? "active" : ""}>
              Add a person
            </Link>
          </nav>
          <div className="tools">
            <label className="inline-select">
              <span>Show times in</span>
              <select value={tz} onChange={(e) => setTz(e.target.value)}>
                {zones.map((z) => (
                  <option key={z} value={z}>
                    {z.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn btn-onteal" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="page">{children}</main>
    </AuthGate>
  );
}
