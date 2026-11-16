import { useEffect, useState } from "react";
import {
  Users, Search, BookOpen, UserPlus, Phone, CreditCard,
  AlertCircle, CheckCircle, RefreshCw, X, ChevronLeft, ChevronRight,
  TrendingDown, TrendingUp, Filter
} from "lucide-react";
import {
  Customer, getCustomers, createCustomer, updateCustomer,
  deactivateCustomer, getCustomerHistory, recordPayment,
  CustomerFinancialHistory, getServiceAreas, AreaItem
} from "./api";

type Props = {
  token: string;
};

export default function CustomersView({ token }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [selectedArea, setSelectedArea] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [areas, setAreas] = useState<AreaItem[]>([]);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [editCustomer, setEditCustomer] = useState<Customer | null>(null);

  // Quick Collect Modal
  const [collectTarget, setCollectTarget] = useState<Customer | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState<"cash" | "upi" | "other">("upi");
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payNotes, setPayNotes] = useState("");
  const [submittingPayment, setSubmittingPayment] = useState(false);
  const [payError, setPayError] = useState("");

  // Passbook (Khata) Modal
  const [khataCustomer, setKhataCustomer] = useState<Customer | null>(null);
  const [khataHistory, setKhataHistory] = useState<CustomerFinancialHistory | null>(null);
  const [loadingKhata, setLoadingKhata] = useState(false);

  // Form states for Add/Edit
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    box_number: "",
    area: "",
    monthly_amount: "",
  });
  const [formError, setFormError] = useState("");
  const [submittingForm, setSubmittingForm] = useState(false);

  // Load service areas for dropdown
  useEffect(() => {
    getServiceAreas(token, false).then(setAreas).catch(() => {});
  }, [token]);

  // Load customer list
  const loadCustomers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getCustomers(token, page, 20, search, includeInactive);
      setCustomers(res.items);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      setError(err.message || "Could not load customers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, [token, page, search, includeInactive]);

  // Filter items in memory by selectedArea if specified
  const displayedCustomers = selectedArea
    ? customers.filter((c) => c.area.toLowerCase() === selectedArea.toLowerCase())
    : customers;

  // Handlers for Add/Edit
  const handleOpenAdd = () => {
    setFormData({
      name: "",
      phone: "",
      box_number: "",
      area: areas.length > 0 ? areas[0].name : "",
      monthly_amount: "",
    });
    setFormError("");
    setShowAddModal(true);
  };

  const handleOpenEdit = (c: Customer) => {
    setEditCustomer(c);
    setFormData({
      name: c.name,
      phone: c.phone,
      box_number: c.box_number,
      area: c.area,
      monthly_amount: c.monthly_amount,
    });
    setFormError("");
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingForm(true);
    setFormError("");
    try {
      if (editCustomer) {
        await updateCustomer(token, editCustomer.id, {
          name: formData.name.trim(),
          phone: formData.phone.trim(),
          box_number: formData.box_number.trim(),
          area: formData.area.trim(),
          monthly_amount: formData.monthly_amount ? formData.monthly_amount : undefined,
        });
        setSuccess("Customer details updated successfully.");
        setEditCustomer(null);
      } else {
        await createCustomer(token, {
          name: formData.name.trim(),
          phone: formData.phone.trim(),
          box_number: formData.box_number.trim(),
          area: formData.area.trim(),
          monthly_amount: formData.monthly_amount ? formData.monthly_amount : undefined,
        });
        setSuccess("New customer registered successfully.");
        setShowAddModal(false);
      }
      loadCustomers();
    } catch (err: any) {
      setFormError(err.message || "Failed to save customer");
    } finally {
      setSubmittingForm(false);
    }
  };

  const handleDeactivate = async (c: Customer) => {
    if (!window.confirm(`Deactivate subscriber "${c.name}" (Box ${c.box_number})? Account and financial records will be preserved.`)) {
      return;
    }
    try {
      await deactivateCustomer(token, c.id);
      setSuccess(`Subscriber ${c.name} deactivated.`);
      loadCustomers();
    } catch (err: any) {
      setError(err.message || "Could not deactivate customer");
    }
  };

  // Quick Collect Handler
  const handleOpenCollect = (c: Customer) => {
    setCollectTarget(c);
    // Prefill with outstanding due, or if 0, prefill with standard monthly amount
    const due = parseFloat(c.current_outstanding_balance || "0");
    const prefill = due > 0 ? c.current_outstanding_balance : c.monthly_amount;
    setPayAmount(prefill);
    setPayMethod("upi");
    setPayDate(new Date().toISOString().slice(0, 10));
    setPayNotes("");
    setPayError("");
  };

  const handleSubmitQuickCollect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!collectTarget) return;
    setSubmittingPayment(true);
    setPayError("");
    try {
      const res = await recordPayment(token, {
        customer_id: collectTarget.id,
        amount: payAmount,
        payment_method: payMethod,
        paid_date: payDate,
        notes: payNotes || undefined,
      });
      setSuccess(`Payment recorded: ₹${res.payment.amount} via ${res.payment.payment_method.toUpperCase()} for ${collectTarget.name} [Receipt: ${res.payment.receipt_number}].`);
      setCollectTarget(null);
      loadCustomers();
    } catch (err: any) {
      setPayError(err.message || "Failed to record payment");
    } finally {
      setSubmittingPayment(false);
    }
  };

  // Passbook (Khata) Handler
  const handleOpenKhata = async (c: Customer) => {
    setKhataCustomer(c);
    setLoadingKhata(true);
    try {
      const hist = await getCustomerHistory(token, c.id);
      setKhataHistory(hist);
    } catch (err: any) {
      alert(err.message || "Could not load customer passbook");
    } finally {
      setLoadingKhata(false);
    }
  };

  return (
    <div className="content">
      {/* Title & Action Bar */}
      <div className="welcome-row">
        <div>
          <p className="eyebrow">OPERATOR WORKSPACE</p>
          <h1>Collection Register</h1>
          <p className="muted">Direct subscriber collection book, dues, and payment passbook.</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button onClick={handleOpenAdd} className="primary-btn" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <UserPlus size={18} /> New Customer
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && <div className="notice" style={{ borderColor: "#ef4444" }}><AlertCircle size={18} color="#ef4444"/><div><strong>Notice</strong><p>{error}</p></div></div>}
      {success && <div className="notice" style={{ borderColor: "#16a34a" }}><CheckCircle size={18} color="#16a34a"/><div><strong>Success</strong><p>{success}</p></div></div>}

      {/* Filters & Search Toolbar */}
      <div className="panel" style={{ padding: 16, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flex: "1 1 300px" }}>
            <div style={{ position: "relative", width: "100%", maxWidth: 360 }}>
              <Search size={18} color="#94a3b8" style={{ position: "absolute", left: 12, top: 11 }} />
              <input
                type="text"
                placeholder="Search by name, phone, or box no..."
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
                <option value="">All Service Areas</option>
                {areas.map((a) => (
                  <option key={a.name} value={a.name}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, cursor: "pointer", color: "#475569" }}>
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => setIncludeInactive(e.target.checked)}
              />
              Show deactivated subscribers
            </label>
            <button onClick={loadCustomers} className="secondary-btn" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Customer Collection Table */}
      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>Loading subscribers...</div>
        ) : displayedCustomers.length === 0 ? (
          <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
            <Users size={40} style={{ margin: "0 auto 12px", opacity: 0.4 }} />
            <p>No subscribers found matching your query.</p>
          </div>
        ) : (
          <>
            {/* Desktop Table View */}
            <div className="desktop-table-container">
              <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                    <th style={{ padding: "12px 16px" }}>Subscriber</th>
                    <th style={{ padding: "12px 16px" }}>Box No</th>
                    <th style={{ padding: "12px 16px" }}>Area</th>
                    <th style={{ padding: "12px 16px" }}>Rate</th>
                    <th style={{ padding: "12px 16px" }}>Current Balance</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedCustomers.map((c) => {
                    const due = parseFloat(c.current_outstanding_balance || "0");
                    const advance = parseFloat(c.advance_credit || "0");

                    return (
                      <tr key={c.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <strong>{c.name}</strong>
                            {!c.is_active && <span className="status-pill status-inactive">Inactive</span>}
                          </div>
                          <div style={{ fontSize: 13, color: "#64748b", display: "flex", alignItems: "center", gap: 4 }}>
                            <Phone size={12} /> {c.phone} · <span style={{ fontFamily: "monospace" }}>{c.display_id}</span>
                          </div>
                        </td>

                        <td style={{ padding: "12px 16px" }}>
                          <span style={{ fontWeight: 600, fontFamily: "monospace", background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>
                            {c.box_number}
                          </span>
                        </td>

                        <td style={{ padding: "12px 16px", color: "#475569" }}>
                          {c.area}
                        </td>

                        <td style={{ padding: "12px 16px", fontWeight: 600 }}>
                          ₹{c.monthly_amount}
                        </td>

                        <td style={{ padding: "12px 16px" }}>
                          {due > 0 ? (
                            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#dc2626", fontWeight: 700 }}>
                              <TrendingDown size={16} /> Due: ₹{c.current_outstanding_balance}
                            </div>
                          ) : advance > 0 ? (
                            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#0284c7", fontWeight: 700 }}>
                              <TrendingUp size={16} /> Advance: ₹{c.advance_credit}
                            </div>
                          ) : (
                            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#16a34a", fontWeight: 700 }}>
                              <CheckCircle size={16} /> Paid / Clear
                            </div>
                          )}
                        </td>

                        <td style={{ padding: "12px 16px", textAlign: "right" }}>
                          <div style={{ display: "inline-flex", gap: 8 }}>
                            <button
                              onClick={() => handleOpenCollect(c)}
                              className="primary-btn"
                              style={{ padding: "6px 12px", fontSize: 13, background: "#16a34a", borderColor: "#16a34a", display: "flex", alignItems: "center", gap: 4 }}
                            >
                              <CreditCard size={14} /> Collect
                            </button>
                            <button
                              onClick={() => handleOpenKhata(c)}
                              className="secondary-btn"
                              style={{ padding: "6px 10px", fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}
                              title="View Customer Passbook"
                            >
                              <BookOpen size={14} /> Khata
                            </button>
                            <button
                              onClick={() => handleOpenEdit(c)}
                              className="secondary-btn"
                              style={{ padding: "6px 10px", fontSize: 13 }}
                            >
                              Edit
                            </button>
                            {c.is_active && (
                              <button
                                onClick={() => handleDeactivate(c)}
                                className="secondary-btn"
                                style={{ padding: "6px 8px", fontSize: 13, color: "#dc2626" }}
                                title="Deactivate Subscriber"
                              >
                                X
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Customer Cards View */}
            <div className="mobile-cards-container">
              {displayedCustomers.map((c) => {
                const due = parseFloat(c.current_outstanding_balance || "0");
                const advance = parseFloat(c.advance_credit || "0");

                return (
                  <article key={c.id} className="customer-mobile-card">
                    <div className="customer-mobile-card-header">
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <strong style={{ fontSize: 15, color: "#0f172a" }}>{c.name}</strong>
                          {!c.is_active && <span className="status-pill status-inactive">Inactive</span>}
                        </div>
                        <div style={{ fontSize: 12, color: "#64748b", display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
                          <Phone size={12} /> {c.phone} · <span style={{ fontFamily: "monospace" }}>{c.display_id}</span>
                        </div>
                      </div>
                      <span style={{ fontWeight: 600, fontFamily: "monospace", background: "#f1f5f9", padding: "3px 8px", borderRadius: 6, fontSize: 12 }}>
                        {c.box_number}
                      </span>
                    </div>

                    <div className="customer-mobile-card-body">
                      <div>
                        <span style={{ color: "#64748b", display: "block", fontSize: 11 }}>Area & Rate</span>
                        <strong style={{ color: "#334155" }}>{c.area} · ₹{c.monthly_amount}/mo</strong>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span style={{ color: "#64748b", display: "block", fontSize: 11 }}>Balance</span>
                        {due > 0 ? (
                          <span style={{ color: "#dc2626", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <TrendingDown size={14} /> Due: ₹{c.current_outstanding_balance}
                          </span>
                        ) : advance > 0 ? (
                          <span style={{ color: "#0284c7", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <TrendingUp size={14} /> Adv: ₹{c.advance_credit}
                          </span>
                        ) : (
                          <span style={{ color: "#16a34a", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <CheckCircle size={14} /> Paid / Clear
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="customer-mobile-card-actions">
                      <button
                        onClick={() => handleOpenCollect(c)}
                        className="primary-btn"
                        style={{ flex: 1, padding: "8px 12px", fontSize: 13, background: "#16a34a", borderColor: "#16a34a", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
                      >
                        <CreditCard size={15} /> Collect
                      </button>
                      <button
                        onClick={() => handleOpenKhata(c)}
                        className="secondary-btn"
                        style={{ padding: "8px 12px", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
                        title="View Customer Passbook"
                      >
                        <BookOpen size={15} /> Khata
                      </button>
                      <button
                        onClick={() => handleOpenEdit(c)}
                        className="secondary-btn"
                        style={{ padding: "8px 12px", fontSize: 13 }}
                      >
                        Edit
                      </button>
                      {c.is_active && (
                        <button
                          onClick={() => handleDeactivate(c)}
                          className="secondary-btn"
                          style={{ padding: "8px 10px", fontSize: 13, color: "#dc2626" }}
                          title="Deactivate Subscriber"
                        >
                          X
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}

        {/* Pagination Bar */}
        <div style={{ padding: 16, display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: 14, color: "#64748b" }}>
            Showing page {page} of {totalPages}
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="secondary-btn"
              style={{ display: "flex", alignItems: "center", gap: 4 }}
            >
              <ChevronLeft size={16} /> Prev
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="secondary-btn"
              style={{ display: "flex", alignItems: "center", gap: 4 }}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* QUICK COLLECT MODAL */}
      {collectTarget && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 440 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h2 style={{ fontSize: 18, margin: 0 }}>Record Received Payment</h2>
                <p className="muted" style={{ margin: "2px 0 0" }}>
                  {collectTarget.name} · Box: <strong>{collectTarget.box_number}</strong>
                </p>
              </div>
              <button className="mobile-close" onClick={() => setCollectTarget(null)}><X size={20}/></button>
            </div>

            {payError && <div className="notice" style={{ borderColor: "#ef4444", marginBottom: 16 }}><AlertCircle size={16} color="#ef4444"/><div><p>{payError}</p></div></div>}

            <form onSubmit={handleSubmitQuickCollect}>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, marginBottom: 16, border: "1px solid #e2e8f0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#64748b" }}>
                  <span>Monthly Rate: ₹{collectTarget.monthly_amount}</span>
                  <span>Pending Dues: <strong style={{ color: "#dc2626" }}>₹{collectTarget.current_outstanding_balance}</strong></span>
                </div>
              </div>

              <label htmlFor="quick-amount">Amount Received (₹)*</label>
              <input
                id="quick-amount"
                type="number"
                step="0.01"
                min="0.01"
                required
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                style={{ fontSize: 18, fontWeight: 700 }}
              />

              <label htmlFor="quick-method">Payment Method*</label>
              <select
                id="quick-method"
                value={payMethod}
                onChange={(e) => setPayMethod(e.target.value as any)}
              >
                <option value="upi">UPI (PhonePe / GPay / Paytm)</option>
                <option value="cash">Cash Received Directly</option>
                <option value="other">Other Offline Mode</option>
              </select>

              <label htmlFor="quick-date">Payment Date*</label>
              <input
                id="quick-date"
                type="date"
                required
                value={payDate}
                onChange={(e) => setPayDate(e.target.value)}
              />

              <label htmlFor="quick-notes">Transaction Reference / Notes (Optional)</label>
              <input
                id="quick-notes"
                type="text"
                placeholder="e.g. UPI Ref #12345 or Collected by Ramesh"
                value={payNotes}
                onChange={(e) => setPayNotes(e.target.value)}
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button type="button" className="secondary-btn" onClick={() => setCollectTarget(null)}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={submittingPayment} style={{ background: "#16a34a", borderColor: "#16a34a" }}>
                  {submittingPayment ? "Saving..." : "Save Payment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CUSTOMER PASSBOOK (KHATA) MODAL */}
      {khataCustomer && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: 680, maxHeight: "90vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h2 style={{ fontSize: 18, margin: 0 }}>Subscriber Passbook (Khata)</h2>
                <p className="muted" style={{ margin: "2px 0 0" }}>
                  {khataCustomer.name} · Box: <strong>{khataCustomer.box_number}</strong> · {khataCustomer.area}
                </p>
              </div>
              <button className="mobile-close" onClick={() => setKhataCustomer(null)}><X size={20}/></button>
            </div>

            {loadingKhata ? (
              <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>Loading passbook history...</div>
            ) : khataHistory ? (
              <div style={{ overflowY: "auto", flex: 1 }}>
                {/* Summary bar */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, background: "#f8fafc", padding: 12, borderRadius: 8, marginBottom: 16 }}>
                  <div>
                    <span style={{ fontSize: 12, color: "#64748b" }}>Monthly Rate</span>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>₹{khataCustomer.monthly_amount}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: 12, color: "#64748b" }}>Total Collected</span>
                    <div style={{ fontWeight: 700, fontSize: 16, color: "#16a34a" }}>₹{khataHistory.total_paid}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: 12, color: "#64748b" }}>Current Balance</span>
                    <div style={{ fontWeight: 700, fontSize: 16, color: parseFloat(khataHistory.outstanding_balance) > 0 ? "#dc2626" : "#16a34a" }}>
                      ₹{khataHistory.outstanding_balance}
                    </div>
                  </div>
                </div>

                {/* Ledger Table */}
                <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#f1f5f9", textAlign: "left" }}>
                      <th style={{ padding: "8px 12px" }}>Date</th>
                      <th style={{ padding: "8px 12px" }}>Description</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Charge (+)</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Paid (-)</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {khataHistory.ledger && khataHistory.ledger.length > 0 ? (
                      khataHistory.ledger.map((entry, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9", background: entry.entry_type === "reversal" ? "#fff1f2" : undefined }}>
                          <td style={{ padding: "8px 12px", whiteSpace: "nowrap", color: "#64748b" }}>{entry.date}</td>
                          <td style={{ padding: "8px 12px" }}>
                            <strong>{entry.description}</strong>
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right", color: parseFloat(entry.charge_amount) > 0 ? "#dc2626" : "#94a3b8" }}>
                            {parseFloat(entry.charge_amount) > 0 ? `+₹${entry.charge_amount}` : "—"}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right", color: parseFloat(entry.payment_amount) > 0 ? "#16a34a" : "#94a3b8" }}>
                            {parseFloat(entry.payment_amount) > 0 ? `-₹${entry.payment_amount}` : "—"}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 700 }}>
                            ₹{entry.running_balance}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", padding: 24, color: "#64748b" }}>
                          No transactions recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}

            <div style={{ marginTop: 16, textAlign: "right" }}>
              <button className="secondary-btn" onClick={() => setKhataCustomer(null)}>Close Passbook</button>
            </div>
          </div>
        </div>
      )}

      {/* ADD / EDIT CUSTOMER MODAL */}
      {(showAddModal || editCustomer) && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2>{editCustomer ? "Edit Subscriber" : "Register New Subscriber"}</h2>
              <button className="mobile-close" onClick={() => { setShowAddModal(false); setEditCustomer(null); }}><X size={20}/></button>
            </div>

            {formError && <div className="notice" style={{ borderColor: "#ef4444", marginBottom: 16 }}><AlertCircle size={16} color="#ef4444"/><div><p>{formError}</p></div></div>}

            <form onSubmit={handleSaveCustomer}>
              <label htmlFor="cust-name">Subscriber Name*</label>
              <input
                id="cust-name"
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />

              <label htmlFor="cust-phone">Phone Number*</label>
              <input
                id="cust-phone"
                type="tel"
                required
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />

              <label htmlFor="cust-box">Set-Top Box Number*</label>
              <input
                id="cust-box"
                type="text"
                required
                value={formData.box_number}
                onChange={(e) => setFormData({ ...formData, box_number: e.target.value })}
              />

              <label htmlFor="cust-area">Service Area*</label>
              <select
                id="cust-area"
                required
                value={formData.area}
                onChange={(e) => setFormData({ ...formData, area: e.target.value })}
              >
                {areas.map((a) => (
                  <option key={a.name} value={a.name}>{a.name}</option>
                ))}
              </select>

              <label htmlFor="cust-rate">Monthly Subscription Rate (₹) [Leave blank for default]</label>
              <input
                id="cust-rate"
                type="number"
                step="0.01"
                min="0.01"
                placeholder="e.g. 350.00"
                value={formData.monthly_amount}
                onChange={(e) => setFormData({ ...formData, monthly_amount: e.target.value })}
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button type="button" className="secondary-btn" onClick={() => { setShowAddModal(false); setEditCustomer(null); }}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={submittingForm}>
                  {submittingForm ? "Saving..." : editCustomer ? "Update Subscriber" : "Create Subscriber"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
