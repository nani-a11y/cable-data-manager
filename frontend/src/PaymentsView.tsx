import { useEffect, useState } from "react";
import {
  Wallet, AlertCircle, CheckCircle, RefreshCw, X, RotateCcw
} from "lucide-react";
import {
  Payment, getPayments, reversePayment
} from "./api";

type Props = {
  token: string;
};

export default function PaymentsView({ token }: Props) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Reversal Modal
  const [reversalTarget, setReversalTarget] = useState<Payment | null>(null);
  const [reversalReason, setReversalReason] = useState("");
  const [reversing, setReversing] = useState(false);

  const loadPayments = async () => {
    setLoading(true);
    try {
      const data = await getPayments(token);
      setPayments(data);
    } catch (err: any) {
      setError(err.message || "Failed to load payment log");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPayments();
  }, [token]);

  const handleReverse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversalTarget) return;
    setReversing(true);
    setError("");
    setSuccess("");
    try {
      await reversePayment(token, reversalTarget.id, reversalReason);
      setSuccess(`Payment receipt ${reversalTarget.receipt_number} reversed. Invoice balances restored.`);
      setReversalTarget(null);
      setReversalReason("");
      loadPayments();
    } catch (err: any) {
      setError(err.message || "Failed to reverse payment");
    } finally {
      setReversing(false);
    }
  };

  return (
    <div className="content">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">AUDIT & TRANSACTION HISTORY</p>
          <h1>Payment Log</h1>
          <p className="muted">Chronological audit log of manual payments received, receipts, and reversals.</p>
        </div>
        <button onClick={loadPayments} className="secondary-btn" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <RefreshCw size={16} /> Refresh Log
        </button>
      </div>

      {error && <div className="notice" style={{ borderColor: "#ef4444" }}><AlertCircle size={18} color="#ef4444"/><div><strong>Notice</strong><p>{error}</p></div></div>}
      {success && <div className="notice" style={{ borderColor: "#16a34a" }}><CheckCircle size={18} color="#16a34a"/><div><strong>Success</strong><p>{success}</p></div></div>}

      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>Loading payment log...</div>
        ) : payments.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
            <Wallet size={40} style={{ margin: "0 auto 12px", opacity: 0.4 }} />
            <p>No payments recorded yet. Collect payments from the Collection Register.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f8fafc", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "12px 16px" }}>Receipt No</th>
                  <th style={{ padding: "12px 16px" }}>Date</th>
                  <th style={{ padding: "12px 16px" }}>Amount (₹)</th>
                  <th style={{ padding: "12px 16px" }}>Method</th>
                  <th style={{ padding: "12px 16px" }}>Reference / Notes</th>
                  <th style={{ padding: "12px 16px" }}>Status</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} style={{ borderBottom: "1px solid #f1f5f9", background: p.is_reversed ? "#fff1f2" : undefined }}>
                    <td style={{ padding: "12px 16px", fontFamily: "monospace", fontWeight: 700 }}>
                      {p.receipt_number}
                    </td>
                    <td style={{ padding: "12px 16px", color: "#475569" }}>
                      {p.paid_date}
                    </td>
                    <td style={{ padding: "12px 16px", fontWeight: 700, color: p.is_reversed ? "#94a3b8" : "#16a34a" }}>
                      ₹{p.amount}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span className="status-pill" style={{ background: "#f1f5f9", color: "#334155", textTransform: "uppercase" }}>
                        {p.payment_method}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", color: "#64748b", fontSize: 13 }}>
                      {p.notes || "—"}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      {p.is_reversed ? (
                        <div>
                          <span className="status-pill status-inactive">REVERSED</span>
                          <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>
                            {p.reversal_reason}
                          </div>
                        </div>
                      ) : (
                        <span className="status-pill status-active">RECORDED</span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      {!p.is_reversed && (
                        <button
                          onClick={() => { setReversalTarget(p); setReversalReason(""); }}
                          className="secondary-btn"
                          style={{ padding: "4px 8px", fontSize: 12, color: "#dc2626" }}
                          title="Reverse this payment entry"
                        >
                          <RotateCcw size={12} style={{ display: "inline", marginRight: 4 }} /> Reverse
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* REVERSAL MODAL */}
      {reversalTarget && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 440 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ fontSize: 18, margin: 0, color: "#dc2626" }}>Reverse Payment Entry</h2>
              <button className="mobile-close" onClick={() => setReversalTarget(null)}><X size={20}/></button>
            </div>

            <p style={{ fontSize: 14, color: "#475569", marginBottom: 16 }}>
              You are about to reverse payment receipt <strong>{reversalTarget.receipt_number}</strong> of <strong>₹{reversalTarget.amount}</strong>.
              Associated customer dues will be restored.
            </p>

            <form onSubmit={handleReverse}>
              <label htmlFor="rev-reason">Reason for Reversal*</label>
              <input
                id="rev-reason"
                type="text"
                required
                placeholder="e.g. Bounced UPI transaction / Wrong entry"
                value={reversalReason}
                onChange={(e) => setReversalReason(e.target.value)}
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button type="button" className="secondary-btn" onClick={() => setReversalTarget(null)}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={reversing} style={{ background: "#dc2626", borderColor: "#dc2626" }}>
                  {reversing ? "Reversing..." : "Confirm Reversal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
