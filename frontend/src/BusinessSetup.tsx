import React, { useState, useEffect } from "react";
import {
  Building2, MapPin, DollarSign, Globe, CheckCircle2,
  AlertTriangle, Plus, X, Loader2, Save
} from "lucide-react";
import { getBusinessSettings, saveBusinessSettings, BusinessSettingsData } from "./api";

interface BusinessSetupProps {
  token: string;
  onSettingsSaved?: (settings: BusinessSettingsData) => void;
}

const COMMON_CURRENCIES = [
  { code: "INR", label: "INR — Indian Rupee (₹)" },
  { code: "USD", label: "USD — US Dollar ($)" },
  { code: "EUR", label: "EUR — Euro (€)" },
  { code: "GBP", label: "GBP — British Pound (£)" },
  { code: "AED", label: "AED — UAE Dirham" },
  { code: "CAD", label: "CAD — Canadian Dollar" },
  { code: "AUD", label: "AUD — Australian Dollar" },
  { code: "SGD", label: "SGD — Singapore Dollar" },
];

const COMMON_TIMEZONES = [
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST, UTC+05:30)" },
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "Asia/Dubai", label: "Asia/Dubai (GST, UTC+04:00)" },
  { value: "Asia/Dhaka", label: "Asia/Dhaka (BST, UTC+06:00)" },
  { value: "Asia/Kathmandu", label: "Asia/Kathmandu (NPT, UTC+05:45)" },
  { value: "Asia/Colombo", label: "Asia/Colombo (IST, UTC+05:30)" },
  { value: "Europe/London", label: "Europe/London (GMT/BST)" },
  { value: "America/New_York", label: "America/New_York (EST/EDT)" },
];

export default function BusinessSetup({ token, onSettingsSaved }: BusinessSetupProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isUpdate, setIsUpdate] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Form fields
  const [businessName, setBusinessName] = useState("");
  const [contactNumber, setContactNumber] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [serviceAreas, setServiceAreas] = useState<string[]>(["Main Area"]);
  const [newAreaInput, setNewAreaInput] = useState("");
  const [currencyCode, setCurrencyCode] = useState("INR");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [defaultMonthlyAmount, setDefaultMonthlyAmount] = useState("300.00");
  const [billingDay, setBillingDay] = useState(1);
  const [gracePeriodDays, setGracePeriodDays] = useState(5);
  const [latePaymentPolicy, setLatePaymentPolicy] = useState("none");

  useEffect(() => {
    let isMounted = true;
    async function load() {
      setLoading(true);
      setErrorMsg("");
      try {
        const data = await getBusinessSettings(token);
        if (data && isMounted) {
          setIsUpdate(true);
          setBusinessName(data.business_name || "");
          setContactNumber(data.contact_number || "");
          setEmail(data.email || "");
          setAddress(data.address || "");
          const stringAreas = (data.service_areas || []).map((a) =>
            typeof a === "string" ? a : a.name
          );
          setServiceAreas(stringAreas);
          setCurrencyCode(data.currency_code || "INR");
          setTimezone(data.timezone || "Asia/Kolkata");
          setDefaultMonthlyAmount(data.default_monthly_amount || "300.00");
          setBillingDay(data.billing_day || 1);
          setGracePeriodDays(data.grace_period_days !== undefined ? data.grace_period_days : 5);
          setLatePaymentPolicy(data.late_payment_policy || "none");
          if (onSettingsSaved) onSettingsSaved(data);
        } else if (isMounted) {
          setIsUpdate(false);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : "Failed to load business settings";
          setErrorMsg(msg);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => { isMounted = false; };
  }, [token]);

  function handleAddArea() {
    const trimmed = newAreaInput.trim();
    if (!trimmed) return;
    if (serviceAreas.some(a => a.toLowerCase() === trimmed.toLowerCase())) {
      setErrorMsg(`Service area "${trimmed}" is already added.`);
      return;
    }
    setServiceAreas([...serviceAreas, trimmed]);
    setNewAreaInput("");
    setErrorMsg("");
  }

  function handleRemoveArea(index: number) {
    if (serviceAreas.length <= 1) {
      setErrorMsg("At least one service area is required.");
      return;
    }
    setServiceAreas(serviceAreas.filter((_, i) => i !== index));
    setErrorMsg("");
  }

  function handleKeyDownArea(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddArea();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSuccessMsg("");
    setErrorMsg("");

    // Client-side validations
    if (!businessName.trim()) {
      setErrorMsg("Business name is required.");
      return;
    }
    if (!contactNumber.trim()) {
      setErrorMsg("Contact phone number is required.");
      return;
    }
    if (serviceAreas.length === 0) {
      setErrorMsg("At least one service area is required.");
      return;
    }
    const parsedAmount = parseFloat(defaultMonthlyAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setErrorMsg("Default monthly amount must be a positive number.");
      return;
    }
    if (billingDay < 1 || billingDay > 28) {
      setErrorMsg("Billing day must be between 1 and 28.");
      return;
    }
    if (gracePeriodDays < 0 || gracePeriodDays > 30) {
      setErrorMsg("Grace period must be between 0 and 30 days.");
      return;
    }

    const payload: BusinessSettingsData = {
      business_name: businessName.trim(),
      contact_number: contactNumber.trim(),
      email: email.trim() ? email.trim() : null,
      address: address.trim() ? address.trim() : null,
      service_areas: serviceAreas,
      currency_code: currencyCode,
      timezone: timezone,
      default_monthly_amount: parseFloat(defaultMonthlyAmount).toFixed(2),
      billing_day: Number(billingDay),
      grace_period_days: Number(gracePeriodDays),
      late_payment_policy: latePaymentPolicy,
    };

    setSaving(true);
    try {
      const saved = await saveBusinessSettings(token, payload, isUpdate);
      setIsUpdate(true);
      setSuccessMsg("Business configuration saved successfully!");
      if (onSettingsSaved) onSettingsSaved(saved);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save configuration";
      setErrorMsg(msg);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="setup-loading-state">
        <Loader2 className="animate-spin" size={32} />
        <p>Loading business configuration…</p>
      </div>
    );
  }

  return (
    <div className="business-setup-container">
      <div className="setup-header">
        <div>
          <p className="eyebrow">CONFIGURATION</p>
          <h1>Business Setup</h1>
          <p className="muted">Configure your cable business profile, operating areas, and billing parameters.</p>
        </div>
        <div className="badge-pill">
          {isUpdate ? "Configured" : "Initial Setup Required"}
        </div>
      </div>

      {successMsg && (
        <div className="alert-banner success">
          <CheckCircle2 size={18} />
          <div>
            <strong>Success</strong>
            <p>{successMsg}</p>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="alert-banner error">
          <AlertTriangle size={18} />
          <div>
            <strong>Validation Error</strong>
            <p>{errorMsg}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="setup-form">
        {/* Section 1: Business Profile */}
        <section className="setup-card">
          <div className="card-title">
            <span className="card-icon"><Building2 size={18} /></span>
            <div>
              <h2>Business Profile</h2>
              <p className="muted">Basic contact details printed on subscriber receipts and statements.</p>
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group full-width">
              <label htmlFor="biz-name">Business Name *</label>
              <input
                id="biz-name"
                type="text"
                value={businessName}
                onChange={e => setBusinessName(e.target.value)}
                placeholder="e.g. City Cable Network"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="biz-phone">Contact Phone Number *</label>
              <input
                id="biz-phone"
                type="tel"
                value={contactNumber}
                onChange={e => setContactNumber(e.target.value)}
                placeholder="e.g. +91 98765 43210"
                required
              />
              <small className="help-text">Used for customer SMS reminders and receipts.</small>
            </div>

            <div className="form-group">
              <label htmlFor="biz-email">Business Email (Optional)</label>
              <input
                id="biz-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="e.g. support@citycable.example"
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="biz-addr">Office / Billing Address (Optional)</label>
              <textarea
                id="biz-addr"
                rows={2}
                value={address}
                onChange={e => setAddress(e.target.value)}
                placeholder="e.g. Shop No. 4, Main Road, Near Bus Stand"
              />
            </div>
          </div>
        </section>

        {/* Section 2: Service Areas */}
        <section className="setup-card">
          <div className="card-title">
            <span className="card-icon"><MapPin size={18} /></span>
            <div>
              <h2>Service Areas</h2>
              <p className="muted">Localities, streets, or sectors where your cable network operates.</p>
            </div>
          </div>

          <div className="areas-container">
            <div className="area-tags-list">
              {serviceAreas.map((area, index) => (
                <span key={index} className="area-chip">
                  <span>{area}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveArea(index)}
                    aria-label={`Remove ${area}`}
                    className="chip-remove"
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>

            <div className="add-area-row">
              <input
                type="text"
                value={newAreaInput}
                onChange={e => setNewAreaInput(e.target.value)}
                onKeyDown={handleKeyDownArea}
                placeholder="Type area name (e.g. Sector 5, Gandhi Nagar)…"
              />
              <button type="button" onClick={handleAddArea} className="btn-secondary">
                <Plus size={16} /> Add Area
              </button>
            </div>
            <small className="help-text">Press Enter or click "Add Area" to include in the service area directory.</small>
          </div>
        </section>

        {/* Section 3: Billing & Subscription Defaults */}
        <section className="setup-card">
          <div className="card-title">
            <span className="card-icon"><DollarSign size={18} /></span>
            <div>
              <h2>Billing & Subscription Defaults</h2>
              <p className="muted">Standard monthly charges and cycle parameters for subscriber invoicing.</p>
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="monthly-amount">Default Monthly Subscription Amount *</label>
              <div className="input-with-prefix">
                <span className="currency-prefix">{currencyCode}</span>
                <input
                  id="monthly-amount"
                  type="number"
                  step="0.01"
                  min="1"
                  value={defaultMonthlyAmount}
                  onChange={e => setDefaultMonthlyAmount(e.target.value)}
                  required
                />
              </div>
              <small className="help-text">Standard default rate applied when adding new customers.</small>
            </div>

            <div className="form-group">
              <label htmlFor="billing-day">Monthly Billing Day (1–28) *</label>
              <input
                id="billing-day"
                type="number"
                min="1"
                max="28"
                value={billingDay}
                onChange={e => setBillingDay(parseInt(e.target.value) || 1)}
                required
              />
              <small className="help-text">Calendar day when invoices are generated each month.</small>
            </div>

            <div className="form-group">
              <label htmlFor="grace-period">Grace Period (Days) *</label>
              <input
                id="grace-period"
                type="number"
                min="0"
                max="30"
                value={gracePeriodDays}
                onChange={e => setGracePeriodDays(parseInt(e.target.value) || 0)}
                required
              />
              <small className="help-text">Days allowed for payment before marking overdue.</small>
            </div>

            <div className="form-group">
              <label htmlFor="late-policy">Late-Payment Policy</label>
              <select
                id="late-policy"
                value={latePaymentPolicy}
                onChange={e => setLatePaymentPolicy(e.target.value)}
              >
                <option value="none">No automated action</option>
                <option value="reminder_only">Send friendly reminder notice</option>
                <option value="suspend_after_grace">Service suspension notice after grace</option>
              </select>
            </div>
          </div>
        </section>

        {/* Section 4: Localization & Timezone */}
        <section className="setup-card">
          <div className="card-title">
            <span className="card-icon"><Globe size={18} /></span>
            <div>
              <h2>Regional & Localization Settings</h2>
              <p className="muted">Ensure invoices and scheduled periods align with your local calendar.</p>
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="currency-select">Currency *</label>
              <select
                id="currency-select"
                value={currencyCode}
                onChange={e => setCurrencyCode(e.target.value)}
              >
                {COMMON_CURRENCIES.map(c => (
                  <option key={c.code} value={c.code}>{c.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="timezone-select">Operational Timezone *</label>
              <select
                id="timezone-select"
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
              >
                {COMMON_TIMEZONES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <div className="form-actions-bar">
          <button type="submit" disabled={saving} className="btn-save-settings">
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Saving Settings…</span>
              </>
            ) : (
              <>
                <Save size={16} />
                <span>{isUpdate ? "Update Configuration" : "Save Initial Configuration"}</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
