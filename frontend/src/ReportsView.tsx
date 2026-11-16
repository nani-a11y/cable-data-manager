import { useEffect, useState } from "react";
import {
  FileText, CheckCircle, ArrowUpRight, AlertCircle, RefreshCw,
  Filter, Search, Printer, Users
} from "lucide-react";
import {
  MonthlyReviewData, getMonthlyReview,
  MonthlyRegisterResponse, getMonthlyRegister,
  getServiceAreas, AreaItem
} from "./api";

type Props = {
  token: string;
};

export default function ReportsView({ token }: Props) {
  const currentMonthStr = new Date().toISOString().slice(0, 7);
  const [selectedMonth, setSelectedMonth] = useState(currentMonthStr);
  const [review, setReview] = useState<MonthlyReviewData | null>(null);
  const [register, setRegister] = useState<MonthlyRegisterResponse | null>(null);
  const [areas, setAreas] = useState<AreaItem[]>([]);
  const [selectedArea, setSelectedArea] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Load service areas
  useEffect(() => {
    getServiceAreas(token, false).then(setAreas).catch(() => {});
  }, [token]);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [revData, regData] = await Promise.all([
        getMonthlyReview(token, selectedMonth),
        getMonthlyRegister(token, selectedMonth, selectedArea || undefined, statusFilter || undefined, search || undefined),
      ]);
      setReview(revData);
      setRegister(regData);
    } catch (err: any) {
      setError(err.message || "Could not load monthly summary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [token, selectedMonth, selectedArea, statusFilter, search]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="content">
      {/* Top Header */}
      <div className="welcome-row">
        <div>
          <p className="eyebrow">MONTHLY PERFORMANCE</p>
          <h1>Monthly Summary</h1>
          <p className="muted">Track month expected revenue, collections, pending balances, and area registers.</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="month"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 14 }}
          />
          <button onClick={loadData} className="secondary-btn" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <RefreshCw size={16} /> Refresh
          </button>
          <button onClick={handlePrint} className="secondary-btn" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Printer size={16} /> Print Sheet
          </button>
        </div>
      </div>

      {error && <div className="notice" style={{ borderColor: "#ef4444" }}><AlertCircle size={18} color="#ef4444"/><div><strong>Error</strong><p>{error}</p></div></div>}

      {/* Top Summary Cards */}
      {review && (
        <div className="stats-grid" style={{ marginBottom: 24 }}>
          <article className="stat-card">
            <div className="stat-top"><span>Expected Dues</span><FileText size={18} /></div>
            <strong>₹{review.estimated_amount}</strong>
            <small>Active subscriber charges for {review.billing_month}</small>
          </article>

          <article className="stat-card">
            <div className="stat-top"><span>Month Collected</span><CheckCircle size={18} color="#16a34a" /></div>
            <strong className="green-value">₹{review.amount_collected}</strong>
            <small>{review.collection_percentage}% collection rate</small>
          </article>

          <article className="stat-card">
            <div className="stat-top"><span>Month Pending</span><ArrowUpRight size={18} color="#dc2626" /></div>
            <strong style={{ color: "#dc2626" }}>₹{review.pending_amount}</strong>
            <small>Uncollected for {review.billing_month}</small>
          </article>

          <article className="stat-card">
            <div className="stat-top"><span>Older Arrears</span><AlertCircle size={18} color="#d97706" /></div>
            <strong style={{ color: "#d97706" }}>₹{review.older_arrears}</strong>
            <small>Unpaid from prior months</small>
          </article>
        </div>
      )}

      {/* Filter Toolbar for Customer-Wise Table */}
      <div className="panel" style={{ padding: 16, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flex: "1 1 300px", flexWrap: "wrap" }}>
            <div style={{ position: "relative", width: "100%", maxWidth: 320 }}>
              <Search size={18} color="#94a3b8" style={{ position: "absolute", left: 12, top: 11 }} />
              <input
                type="text"
                placeholder="Search subscriber or box..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: "100%", paddingLeft: 38, paddingRight: 12, height: 40, borderRadius: 8, border: "1px solid #cbd5e1" }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Filter size={16} color="#64748b" />
              <select
                value={selectedArea}
                onChange={(e) => setSelectedArea(e.target.value)}
                style={{ height: 40, borderRadius: 8, border: "1px solid #cbd5e1", padding: "0 10px" }}
              >
                <option value="">All Areas</option>
                {areas.map((a) => (
                  <option key={a.name} value={a.name}>{a.name}</option>
                ))}
              </select>
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ height: 40, borderRadius: 8, border: "1px solid #cbd5e1", padding: "0 10px" }}
            >
              <option value="">All Statuses</option>
              <option value="paid">Paid (Fully Collected)</option>
              <option value="partial">Partial Payment</option>
              <option value="unpaid">Unpaid (No Payment)</option>
            </select>
          </div>

          <div style={{ fontSize: 13, color: "#64748b" }}>
            {register ? (
              <span>
                Filtered: <strong>{register.total_customers}</strong> subscribers · Expected: <strong>₹{register.total_expected}</strong> · Collected: <strong style={{ color: "#16a34a" }}>₹{register.total_collected}</strong>
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {/* Customer-Wise Collection Register Table */}
      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>Loading collection sheet...</div>
        ) : !register || register.items.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
            <Users size={40} style={{ margin: "0 auto 12px", opacity: 0.4 }} />
            <p>No subscribers matching current filter criteria.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f8fafc", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "12px 16px" }}>Subscriber</th>
                  <th style={{ padding: "12px 16px" }}>Box No</th>
                  <th style={{ padding: "12px 16px" }}>Area</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Due (₹)</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Paid (₹)</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Balance (₹)</th>
                  <th style={{ padding: "12px 16px", textAlign: "center" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {register.items.map((item) => (
                  <tr key={item.customer_id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "12px 16px" }}>
                      <strong>{item.customer_name}</strong>
                      <div style={{ fontSize: 13, color: "#64748b" }}>{item.phone} · <span style={{ fontFamily: "monospace" }}>{item.display_id}</span></div>
                    </td>
                    <td style={{ padding: "12px 16px", fontFamily: "monospace", fontWeight: 600 }}>
                      {item.box_number}
                    </td>
                    <td style={{ padding: "12px 16px", color: "#475569" }}>
                      {item.area}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600 }}>
                      ₹{item.amount_due}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", color: parseFloat(item.amount_collected) > 0 ? "#16a34a" : "#94a3b8", fontWeight: 600 }}>
                      ₹{item.amount_collected}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", color: parseFloat(item.pending_amount) > 0 ? "#dc2626" : "#16a34a", fontWeight: 700 }}>
                      ₹{item.pending_amount}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "center" }}>
                      <span className={`status-pill ${item.status === "paid" ? "status-active" : item.status === "partial" ? "status-pending" : "status-inactive"}`}>
                        {item.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
