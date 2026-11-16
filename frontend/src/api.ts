const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type BusinessSettingsData = {
  id?: number;
  business_name: string;
  contact_number: string;
  email?: string | null;
  address?: string | null;
  service_areas: string[];
  currency_code: string;
  timezone: string;
  default_monthly_amount: string;
  billing_day: number;
  grace_period_days: number;
  late_payment_policy?: string | null;
  created_at?: string;
  updated_at?: string;
};

export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!response.ok) throw new Error("Invalid email or password");
  return response.json() as Promise<{ access_token: string; token_type: string }>;
}

export async function getDashboard(token: string) {
  const response = await fetch(`${API_URL}/api/dashboard/summary`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error("Could not load dashboard");
  return response.json();
}

export async function getBusinessSettings(token: string): Promise<BusinessSettingsData | null> {
  const response = await fetch(`${API_URL}/api/business-settings`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Could not fetch business settings");
  }
  return response.json();
}

export async function saveBusinessSettings(
  token: string,
  data: BusinessSettingsData,
  isUpdate: boolean
): Promise<BusinessSettingsData> {
  const method = isUpdate ? "PUT" : "POST";
  const response = await fetch(`${API_URL}/api/business-settings`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    if (errorData.detail && Array.isArray(errorData.detail)) {
      const messages = errorData.detail.map((err: { msg?: string; loc?: string[] }) => {
        const field = err.loc && err.loc.length > 1 ? `${err.loc[err.loc.length - 1]}: ` : "";
        return `${field}${err.msg}`;
      }).join("; ");
      throw new Error(messages);
    }
    throw new Error(errorData.detail || "Failed to save business settings");
  }
  return response.json();
}
