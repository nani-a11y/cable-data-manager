import { useEffect, useState } from "react";
import {
  Cable, LayoutDashboard, Users, Wallet, MapPin, FileSpreadsheet,
  ChartNoAxesCombined, Settings, LogOut, Bell, ShieldCheck,
  Menu, X, CircleDollarSign, ArrowUpRight, Clock3
} from "lucide-react";
import { getDashboard, login } from "./api";

type Summary = {
  total_customers: number;
  expected_collection: number;
  collected: number;
  outstanding: number;
  data_status: string;
};

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "Customers", icon: Users },
  { label: "Payments", icon: Wallet },
  { label: "Areas", icon: MapPin },
  { label: "Excel Import", icon: FileSpreadsheet },
  { label: "Reports", icon: ChartNoAxesCombined },
  { label: "Settings", icon: Settings }
];

function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("cable_token") || "");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);

  useEffect(() => {
    if (!token) return;
    getDashboard(token).then(setSummary).catch(() => {
      localStorage.removeItem("cable_token");
      setToken("");
    });
  }, [token]);

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const formData = new FormData(e.currentTarget);
    const submittedEmail = formData.get("email");
    const submittedPassword = formData.get("password");

    if (
      typeof submittedEmail !== "string" ||
      !submittedEmail.trim() ||
      typeof submittedPassword !== "string" ||
      submittedPassword.length === 0
    ) {
      setError("Enter your admin email and password.");
      return;
    }

    setLoading(true);
    try {
      const result = await login(submittedEmail, submittedPassword);
      localStorage.setItem("cable_token", result.access_token);
      setToken(result.access_token);
      setPassword("");
    } catch {
      setError("Login failed. Check your admin email and password.");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("cable_token");
    setToken("");
    setSummary(null);
  }

  if (!token) {
    return (
      <main className="login-wrap">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand-mark"><Cable size={25} /></div>
          <p className="eyebrow">CABLE OPERATOR MANAGEMENT</p>
          <h1>Welcome back</h1>
          <p className="muted">Sign in to manage your cable business.</p>
          <label htmlFor="admin-email">Admin email</label>
          <input id="admin-email" name="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="username" />
          <label htmlFor="admin-password">Password</label>
          <input id="admin-password" name="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" />
          {error && <p className="error">{error}</p>}
          <button className="primary-btn" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
          <p className="login-foot"><ShieldCheck size={15} /> Secure administrator access</p>
        </form>
      </main>
    );
  }

  return (
    <div className="app-shell">
      {mobileMenu && <button className="scrim" onClick={() => setMobileMenu(false)} aria-label="Close menu" />}
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand"><span className="brand-mark"><Cable size={22} /></span><span>Cable<span className="brand-light">Manager</span></span>
          <button className="mobile-close" onClick={() => setMobileMenu(false)}><X size={20}/></button>
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav>{navItems.map(item => {
          const Icon = item.icon;
          return <button key={item.label} className={`nav-item ${item.active ? "active" : ""}`} onClick={() => item.label !== "Dashboard" && alert(`${item.label} will be implemented in the next phase.`)}>
            <Icon size={18}/><span>{item.label}</span>{item.active && <span className="active-dot"/>}
          </button>;
        })}</nav>
        <div className="sidebar-bottom"><div className="admin-chip"><div className="avatar">A</div><div><strong>Administrator</strong><small>Owner access</small></div></div></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileMenu(true)}><Menu size={21}/></button>
          <div className="breadcrumb">Workspace <span>/</span> <strong>Dashboard</strong></div>
          <div className="top-actions"><button className="icon-btn" aria-label="Notifications"><Bell size={18}/></button><span className="top-divider"/><button className="profile-btn" onClick={logout}><span className="avatar">A</span><span className="profile-name">Admin</span><LogOut size={16}/></button></div>
        </header>

        <section className="content">
          <div className="welcome-row"><div><p className="eyebrow">OVERVIEW</p><h1>Dashboard</h1><p className="muted">Your cable business at a glance.</p></div><div className="date-pill"><Clock3 size={15}/> {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</div></div>

          <div className="notice"><ShieldCheck size={18}/><div><strong>Phase 1 foundation is ready</strong><p>Admin authentication and cloud database connection are configured. Import customer records in Phase 2 to activate live business metrics.</p></div></div>

          <div className="stats-grid">
            <Stat title="Total customers" value={summary ? String(summary.total_customers) : "—"} icon={<Users/>} note="Customer records will appear after import"/>
            <Stat title="Expected collection" value={summary ? money(summary.expected_collection) : "—"} icon={<CircleDollarSign/>} note="Monthly billing total"/>
            <Stat title="Collected this month" value={summary ? money(summary.collected) : "—"} icon={<Wallet/>} note="Confirmed payments only" positive/>
            <Stat title="Outstanding balance" value={summary ? money(summary.outstanding) : "—"} icon={<ArrowUpRight/>} note="Unpaid and partial balances"/>
          </div>

          <div className="lower-grid">
            <section className="panel collection-panel"><div className="panel-heading"><div><h2>Monthly collection</h2><p className="muted">Payment progress for the selected month</p></div><span className="tag">Live data pending</span></div>
              <div className="empty-chart"><div className="empty-icon"><ChartNoAxesCombined size={28}/></div><strong>Collection chart will appear here</strong><p>Once customer bills and payments are added, this chart will show collected vs. outstanding amounts.</p></div>
            </section>
            <section className="panel"><div className="panel-heading"><div><h2>Quick overview</h2><p className="muted">Your workspace modules</p></div></div>
              <div className="module-list"><Module icon={<Users/>} title="Customer directory" desc="Search and manage customers" status="Phase 3"/><Module icon={<Wallet/>} title="Payment tracking" desc="Full and partial payments" status="Phase 4"/><Module icon={<FileSpreadsheet/>} title="Excel import" desc="Bring in existing records" status="Phase 2"/><Module icon={<Settings/>} title="Admin settings" desc="Default and custom pricing" status="Phase 3"/></div>
            </section>
          </div>
          <footer>© {new Date().getFullYear()} Cable Manager <span>Secure business workspace</span></footer>
        </section>
      </main>
    </div>
  );
}

function Stat({ title, value, icon, note, positive = false }: { title: string; value: string; icon: React.ReactNode; note: string; positive?: boolean }) {
  return <article className="stat-card"><div className="stat-top"><span>{title}</span><span className="stat-icon">{icon}</span></div><strong className={positive ? "green-value" : ""}>{value}</strong><small>{note}</small></article>;
}
function Module({ icon, title, desc, status }: { icon: React.ReactNode; title: string; desc: string; status: string }) {
  return <div className="module-row"><span className="module-icon">{icon}</span><div className="module-copy"><strong>{title}</strong><small>{desc}</small></div><span className="phase-tag">{status}</span></div>;
}
