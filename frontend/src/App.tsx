import { useEffect, useState } from "react";
import {
  Cable, LayoutDashboard, Users, Wallet,
  ChartNoAxesCombined, Settings, LogOut, ShieldCheck,
  Menu, X, CircleDollarSign, ArrowUpRight, Clock3, BookOpen,
  MapPin, FileText, Eye, EyeOff
} from "lucide-react";
import { getDashboard, login } from "./api";
import BusinessSetup from "./BusinessSetup";
import CustomersView from "./CustomersView";
import PaymentsView from "./PaymentsView";
import ReportsView from "./ReportsView";
import BillingView from "./BillingView";
import AreasView from "./AreasView";

type Summary = {
  total_customers: number;
  expected_collection: number;
  collected: number;
  outstanding: number;
  data_status: string;
};

type TabType = "Dashboard" | "Collection Register" | "Billing" | "Monthly Summary" | "Payment Log" | "Service Areas" | "Settings";

const navItems = [
  { id: "Dashboard" as TabType, label: "Dashboard", icon: LayoutDashboard },
  { id: "Collection Register" as TabType, label: "Collection Register", icon: Users },
  { id: "Billing" as TabType, label: "Billing Management", icon: FileText },
  { id: "Monthly Summary" as TabType, label: "Monthly Summary", icon: ChartNoAxesCombined },
  { id: "Payment Log" as TabType, label: "Payment Log", icon: Wallet },
  { id: "Service Areas" as TabType, label: "Service Areas", icon: MapPin },
  { id: "Settings" as TabType, label: "Settings", icon: Settings }
];

function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("cable_token") || "");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("Dashboard");

  useEffect(() => {
    if (!token) return;
    getDashboard(token).then(setSummary).catch(() => {
      localStorage.removeItem("cable_token");
      setToken("");
    });
  }, [token, activeTab]);

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
          <div className="password-input-wrap">
            <input
              id="admin-password"
              name="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <button
              type="button"
              className="password-toggle-btn"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              title={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
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
          const isActive = activeTab === item.id;
          return <button key={item.label} className={`nav-item ${isActive ? "active" : ""}`} onClick={() => {
            setActiveTab(item.id);
            setMobileMenu(false);
          }}>
            <Icon size={18}/><span>{item.label}</span>{isActive && <span className="active-dot"/>}
          </button>;
        })}</nav>
        <div className="sidebar-bottom"><div className="admin-chip"><div className="avatar">A</div><div><strong>Administrator</strong><small>Owner access</small></div></div></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileMenu(true)}><Menu size={21}/></button>
          <div className="breadcrumb">Workspace <span>/</span> <strong>{activeTab}</strong></div>
          <div className="top-actions"><button className="profile-btn" onClick={logout}><span className="avatar">A</span><span className="profile-name">Admin</span><LogOut size={16}/></button></div>
        </header>

        {activeTab === "Settings" && <BusinessSetup token={token} />}
        {activeTab === "Collection Register" && <CustomersView token={token} />}
        {activeTab === "Billing" && <BillingView token={token} />}
        {activeTab === "Payment Log" && <PaymentsView token={token} />}
        {activeTab === "Monthly Summary" && <ReportsView token={token} />}
        {activeTab === "Service Areas" && <AreasView token={token} />}

        {activeTab === "Dashboard" && (
          <section className="content">
            <div className="welcome-row"><div><p className="eyebrow">COLLECTION REGISTER</p><h1>Operator Dashboard</h1><p className="muted">Your local cable TV subscription and collection ledger.</p></div><div className="date-pill"><Clock3 size={15}/> {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</div></div>

            <div className="stats-grid">
              <Stat title="Total active subscribers" value={summary ? String(summary.total_customers) : "—"} icon={<Users/>} note="Registered active boxes"/>
              <Stat title="Expected dues" value={summary ? money(summary.expected_collection) : "—"} icon={<CircleDollarSign/>} note="Current month dues"/>
              <Stat title="Collected this month" value={summary ? money(summary.collected) : "—"} icon={<Wallet/>} note="Confirmed cash & UPI" positive/>
              <Stat title="Pending balance" value={summary ? money(summary.outstanding) : "—"} icon={<ArrowUpRight/>} note="Total outstanding balance"/>
            </div>

            <div className="lower-grid">
              <section className="panel collection-panel">
                <div className="panel-heading">
                  <div><h2>Quick Actions</h2><p className="muted">Direct operator shortcuts</p></div>
                </div>
                <div className="quick-actions-grid">
                  <button onClick={() => setActiveTab("Collection Register")} className="secondary-btn quick-action-tile">
                    <Users size={24} className="icon-sky" />
                    <strong>Collection Register</strong>
                    <small>Collect dues, view khata, and manage subscribers</small>
                  </button>
                  <button onClick={() => setActiveTab("Billing")} className="secondary-btn quick-action-tile">
                    <FileText size={24} className="icon-cyan" />
                    <strong>Billing Management</strong>
                    <small>Monthly invoice cycle & overdue catch-up</small>
                  </button>
                  <button onClick={() => setActiveTab("Monthly Summary")} className="secondary-btn quick-action-tile">
                    <ChartNoAxesCombined size={24} className="icon-green" />
                    <strong>Monthly Summary</strong>
                    <small>Area-wise collection sheet & print register</small>
                  </button>
                  <button onClick={() => setActiveTab("Payment Log")} className="secondary-btn quick-action-tile">
                    <Wallet size={24} className="icon-amber" />
                    <strong>Payment Log</strong>
                    <small>Receipts, notes, and audit reversals</small>
                  </button>
                  <button onClick={() => setActiveTab("Service Areas")} className="secondary-btn quick-action-tile">
                    <MapPin size={24} className="icon-rose" />
                    <strong>Service Areas</strong>
                    <small>Add zones and update area subscriber rates</small>
                  </button>
                  <button onClick={() => setActiveTab("Settings")} className="secondary-btn quick-action-tile">
                    <Settings size={24} className="icon-purple" />
                    <strong>Settings</strong>
                    <small>Service areas, default rate & business profile</small>
                  </button>
                </div>
              </section>

              <section className="panel">
                <div className="panel-heading"><div><h2>Register Status</h2><p className="muted">System health</p></div></div>
                <div className="module-list">
                  <Module icon={<Users/>} title="Subscriber Register" desc="Active boxes & live balance" status="Ready" onClick={() => setActiveTab("Collection Register")} />
                  <Module icon={<BookOpen/>} title="Customer Khata" desc="Chronological passbook statements" status="Ready" onClick={() => setActiveTab("Collection Register")} />
                  <Module icon={<Wallet/>} title="Payment Receipts" desc="Cash & UPI manual recording" status="Ready" onClick={() => setActiveTab("Payment Log")} />
                  <Module icon={<Settings/>} title="Business Rules" desc="Service areas & rates" status="Ready" onClick={() => setActiveTab("Settings")} />
                </div>
              </section>
            </div>
            <footer>© {new Date().getFullYear()} Cable Manager <span>Offline collection register for local cable operators</span></footer>
          </section>
        )}
      </main>
    </div>
  );
}

function Stat({ title, value, icon, note, positive = false }: { title: string; value: string; icon: React.ReactNode; note: string; positive?: boolean }) {
  return <article className="stat-card"><div className="stat-top"><span>{title}</span><span className="stat-icon">{icon}</span></div><strong className={positive ? "green-value" : ""}>{value}</strong><small>{note}</small></article>;
}
function Module({ icon, title, desc, status, onClick }: { icon: React.ReactNode; title: string; desc: string; status: string; onClick?: () => void }) {
  return (
    <div
      className={`module-row ${onClick ? "clickable" : ""}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={onClick ? { cursor: "pointer" } : undefined}
    >
      <span className="module-icon">{icon}</span>
      <div className="module-copy"><strong>{title}</strong><small>{desc}</small></div>
      <span className="phase-tag" style={{ background: "#dcfce7", color: "#166534" }}>{status}</span>
    </div>
  );
}
