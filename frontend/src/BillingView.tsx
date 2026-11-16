import { useEffect, useState } from "react";
import {
  FileText, Play, AlertCircle, CheckCircle, Calendar, ArrowUpRight
} from "lucide-react";
import { Invoice, getInvoices, triggerMonthlyBilling } from "./api";

type Props = {
  token: string;
};

export default function BillingView({ token }: Props) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const currentMonthStr = new Date().toISOString().slice(0, 7);
  const [selectedMonth, setSelectedMonth] = useState(currentMonthStr);
  const [generating, setGenerating] = useState(false);

  const loadInvoices = async () => {
    setLoading(true);
    try {
      const data = await getInvoices(token, undefined, selectedMonth);
      setInvoices(data);
    } catch (err: any) {
      setError(err.message || "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, [token, selectedMonth]);

  const handleGenerate = async () => {
    if (!window.confirm(`Generate bills for month ${selectedMonth}? Invoices will be created for all active customers.`)) {
      return;
    }
    setGenerating(true);
    setError("");
    setSuccess("");
    try {
      const res = await triggerMonthlyBilling(token, selectedMonth);
      setSuccess(`Billing completed: ${res.invoices_created} new invoices created (₹${res.total_billed_amount}), ${res.already_existing} already existed.`);
      loadInvoices();
    } catch (err: any) {
      setError(err.message || "Failed to generate monthly bills");
    } finally {
      setGenerating(false);
    }
  };

  const totalBilled = invoices.reduce((acc, i) => acc + parseFloat(i.amount), 0);
  const totalPaid = invoices.reduce((acc, i) => acc + parseFloat(i.paid_amount), 0);
  const totalPending = totalBilled - totalPaid;

  return (
    <div className="content">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">BILLING & INVOICES</p>
          <h1>Monthly Invoices</h1>
          <p className="muted">Generate and track monthly cable bills for subscribers.</p>
        </div>
        <button
          className="primary-btn"
          disabled={generating}
          onClick={handleGenerate}
          style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          <Play size={18} /> {generating ? "Generating..." : "Generate Month Bills"}
        </button>
      </div>

      {error && <div className="notice" style={{ borderColor: "#ef4444" }}><AlertCircle size={18} color="#ef4444"/><div><strong>Error</strong><p>{error}</p></div></div>}
      {success && <div className="notice" style={{ borderColor: "#16a34a" }}><CheckCircle size={18} color="#16a34a"/><div><strong>Success</strong><p>{success}</p></div></div>}

      <div className="stats-grid" style={{ marginBottom: 24 }}>
        <article className="stat-card">
          <div className="stat-top"><span>Month Billed</span><FileText size={18} /></div>
          <strong>₹{totalBilled.toFixed(2)}</strong>
          <small>{invoices.length} invoices issued</small>
        </article>
        <article className="stat-card">
          <div className="stat-top"><span>Collected</span><CheckCircle size={18} color="#16a34a" /></div>
          <strong className="green-value">₹{totalPaid.toFixed(2)}</strong>
          <small>Allocated payments</small>
        </article>
        <article className="stat-card">
          <div className="stat-top"><span>Outstanding</span><ArrowUpRight size={18} color="#dc2626" /></div>
          <strong style={{ color: "#dc2626" }}>₹{totalPending.toFixed(2)}</strong>
          <small>Pending balance</small>
        </article>
      </div>

      <div className="panel" style={{ padding: 20, marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Calendar size={18} className="muted" />
            <label style={{ fontSize: 14, fontWeight: 500 }}>Select Billing Month:</label>
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              style={{ padding: "6px 12px", borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 14 }}
            />
          </div>
          <button onClick={loadInvoices} className="secondary-btn" style={{ padding: "6px 14px" }}>
            Refresh Invoices
          </button>
        </div>
      </div>

      <div className="panel" style={{ padding: 0, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
              <th style={{ padding: "12px 16px" }}>Invoice #</th>
              <th style={{ padding: "12px 16px" }}>Customer ID</th>
              <th style={{ padding: "12px 16px" }}>Billing Month</th>
              <th style={{ padding: "12px 16px" }}>Bill Amount</th>
              <th style={{ padding: "12px 16px" }}>Paid Amount</th>
              <th style={{ padding: "12px 16px" }}>Pending</th>
              <th style={{ padding: "12px 16px" }}>Issued Date</th>
              <th style={{ padding: "12px 16px" }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 32, textAlign: "center", color: "#64748b" }}>Loading invoices...</td></tr>
            ) : invoices.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: 32, textAlign: "center", color: "#64748b" }}>No invoices found for {selectedMonth}. Click "Generate Month Bills" above.</td></tr>
            ) : (
              invoices.map((inv) => {
                const pending = (parseFloat(inv.amount) - parseFloat(inv.paid_amount)).toFixed(2);
                return (
                  <tr key={inv.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "12px 16px", fontWeight: 600 }}>{inv.invoice_number}</td>
                    <td style={{ padding: "12px 16px" }}>Customer #{inv.customer_id}</td>
                    <td style={{ padding: "12px 16px" }}>{inv.billing_month}</td>
                    <td style={{ padding: "12px 16px", fontWeight: 600 }}>₹{inv.amount}</td>
                    <td style={{ padding: "12px 16px", color: "#16a34a" }}>₹{inv.paid_amount}</td>
                    <td style={{ padding: "12px 16px", color: parseFloat(pending) > 0 ? "#dc2626" : "#64748b" }}>₹{pending}</td>
                    <td style={{ padding: "12px 16px" }}>{inv.issued_date}</td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 12, fontSize: 12, fontWeight: 600,
                        background: inv.status === "paid" ? "#dcfce7" : inv.status === "partial" ? "#fef3c7" : "#fee2e2",
                        color: inv.status === "paid" ? "#166534" : inv.status === "partial" ? "#854d0e" : "#991b1b"
                      }}>
                        {inv.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
