const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type BusinessSettingsData = {
  id?: number;
  business_name: string;
  contact_number: string;
  email?: string | null;
  address?: string | null;
  service_areas: (string | { name: string; is_active: boolean })[];
  currency_code: string;
  timezone: string;
  default_monthly_amount: string;
  billing_day: number;
  grace_period_days: number;
  late_payment_policy?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type AreaItem = {
  name: string;
  is_active: boolean;
  customer_count: number;
};

export type Customer = {
  id: number;
  display_id: string;
  name: string;
  phone: string;
  box_number: string;
  area: string;
  monthly_amount: string;
  is_active: boolean;
  current_outstanding_balance: string;
  advance_credit: string;
  created_at: string;
  updated_at: string;
};

export type CustomerPagination = {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type Invoice = {
  id: number;
  invoice_number: string;
  customer_id: number;
  billing_month: string;
  amount: string;
  paid_amount: string;
  status: "pending" | "partial" | "paid";
  issued_date: string;
  created_at: string;
  updated_at: string;
};

export type Payment = {
  id: number;
  receipt_number: string;
  customer_id: number;
  amount: string;
  payment_method: "cash" | "upi" | "other";
  paid_date: string;
  notes?: string | null;
  is_reversed: boolean;
  reversal_reason?: string | null;
  reversed_at?: string | null;
  created_at: string;
};

export type LedgerEntry = {
  date: string;
  entry_type: "charge" | "payment" | "reversal";
  description: string;
  charge_amount: string;
  payment_amount: string;
  running_balance: string;
};

export type CustomerFinancialHistory = {
  customer: Customer;
  total_invoiced: string;
  total_paid: string;
  outstanding_balance: string;
  advance_credit: string;
  invoices: Invoice[];
  payments: Payment[];
  ledger: LedgerEntry[];
};

export type MonthlyRegisterItem = {
  customer_id: number;
  display_id: string;
  customer_name: string;
  phone: string;
  box_number: string;
  area: string;
  monthly_amount: string;
  amount_due: string;
  amount_collected: string;
  pending_amount: string;
  status: "paid" | "partial" | "unpaid";
  is_active: boolean;
};

export type MonthlyRegisterResponse = {
  billing_month: string;
  total_customers: number;
  total_expected: string;
  total_collected: string;
  total_pending: string;
  items: MonthlyRegisterItem[];
};

export type MonthlyReviewData = {
  billing_month: string;
  is_invoice_backed: boolean;
  estimated_amount: string;
  amount_collected: string;
  pending_amount: string;
  collection_percentage: number;
  older_arrears: string;
  advance_credit: string;
  total_active_customers: number;
  total_inactive_customers: number;
};

// --- API Helpers ---

async function handleResponse<T>(res: Response, fallbackError: string): Promise<T> {
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    if (errorData.detail && Array.isArray(errorData.detail)) {
      const messages = errorData.detail
        .map((err: { msg?: string; loc?: string[] }) => {
          const field = err.loc && err.loc.length > 1 ? `${err.loc[err.loc.length - 1]}: ` : "";
          return `${field}${err.msg}`;
        })
        .join("; ");
      throw new Error(messages);
    }
    throw new Error(errorData.detail || fallbackError);
  }
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<{ access_token: string; token_type: string }>(response, "Invalid email or password");
}

export async function getDashboard(token: string) {
  const response = await fetch(`${API_URL}/api/dashboard/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<{
    total_customers: number;
    expected_collection: number;
    collected: number;
    outstanding: number;
    data_status: string;
  }>(response, "Could not load dashboard");
}

export async function getBusinessSettings(token: string): Promise<BusinessSettingsData | null> {
  const response = await fetch(`${API_URL}/api/business-settings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 404) return null;
  return handleResponse<BusinessSettingsData>(response, "Could not fetch business settings");
}

export async function saveBusinessSettings(
  token: string,
  data: BusinessSettingsData,
  isUpdate: boolean,
): Promise<BusinessSettingsData> {
  const method = isUpdate ? "PUT" : "POST";
  const response = await fetch(`${API_URL}/api/business-settings`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<BusinessSettingsData>(response, "Failed to save business settings");
}

// --- Service Areas & Rates ---

export async function getServiceAreas(token: string, includeArchived = true): Promise<AreaItem[]> {
  const response = await fetch(`${API_URL}/api/business-settings/areas?include_archived=${includeArchived}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<AreaItem[]>(response, "Could not fetch service areas");
}

export async function addServiceArea(token: string, name: string) {
  const response = await fetch(`${API_URL}/api/business-settings/areas`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name }),
  });
  return handleResponse<{ message: string }>(response, "Could not add service area");
}

export async function renameServiceArea(token: string, old_name: string, new_name: string) {
  const response = await fetch(`${API_URL}/api/business-settings/areas/rename`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ old_name, new_name }),
  });
  return handleResponse<{ message: string; updated_customers: number }>(response, "Could not rename area");
}

export async function archiveServiceArea(token: string, name: string, is_active: boolean) {
  const response = await fetch(`${API_URL}/api/business-settings/areas/archive`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name, is_active }),
  });
  return handleResponse<{ message: string }>(response, "Could not update area status");
}

export async function bulkRateUpdate(token: string, new_monthly_amount: string, confirm: boolean) {
  const response = await fetch(`${API_URL}/api/business-settings/bulk-rate-update`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ new_monthly_amount, confirm }),
  });
  return handleResponse<{ affected_customers_count: number; new_monthly_amount: string; message: string }>(
    response,
    "Could not update rates",
  );
}

// --- Customer APIs ---

export async function getCustomers(
  token: string,
  page = 1,
  pageSize = 20,
  search?: string,
  includeInactive = false,
): Promise<CustomerPagination> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    include_inactive: String(includeInactive),
  });
  if (search) params.append("search", search);

  const response = await fetch(`${API_URL}/api/customers?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<CustomerPagination>(response, "Could not load customers");
}

export async function getCustomer(token: string, id: number): Promise<Customer> {
  const response = await fetch(`${API_URL}/api/customers/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<Customer>(response, "Customer not found");
}

export async function createCustomer(
  token: string,
  data: { name: string; phone: string; box_number: string; area: string; monthly_amount?: string },
): Promise<Customer> {
  const response = await fetch(`${API_URL}/api/customers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<Customer>(response, "Could not create customer");
}

export async function updateCustomer(
  token: string,
  id: number,
  data: Partial<{ name: string; phone: string; box_number: string; area: string; monthly_amount: string; is_active: boolean }>,
): Promise<Customer> {
  const response = await fetch(`${API_URL}/api/customers/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<Customer>(response, "Could not update customer");
}

export async function deactivateCustomer(token: string, id: number): Promise<Customer> {
  const response = await fetch(`${API_URL}/api/customers/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<Customer>(response, "Could not deactivate customer");
}

export async function getCustomerHistory(token: string, id: number): Promise<CustomerFinancialHistory> {
  const response = await fetch(`${API_URL}/api/customers/${id}/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<CustomerFinancialHistory>(response, "Could not load customer financial history");
}

// --- Billing APIs ---

export async function triggerMonthlyBilling(token: string, billingMonth: string) {
  const response = await fetch(`${API_URL}/api/billing/generate/${billingMonth}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<{
    billing_month: string;
    eligible_customers: number;
    invoices_created: number;
    already_existing: number;
    total_billed_amount: string;
  }>(response, "Billing generation failed");
}

export async function getInvoices(token: string, customerId?: number, billingMonth?: string): Promise<Invoice[]> {
  const params = new URLSearchParams();
  if (customerId) params.append("customer_id", String(customerId));
  if (billingMonth) params.append("billing_month", billingMonth);

  const response = await fetch(`${API_URL}/api/billing/invoices?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<Invoice[]>(response, "Could not load invoices");
}

// --- Payments APIs ---

export async function recordPayment(
  token: string,
  data: {
    customer_id: number;
    amount: string;
    payment_method: "cash" | "upi" | "other";
    paid_date: string;
    notes?: string;
  },
) {
  const response = await fetch(`${API_URL}/api/payments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<{
    payment: Payment;
    allocated_invoices_count: number;
    total_allocated: string;
    advance_credit_remaining: string;
    message: string;
  }>(response, "Failed to record payment");
}

export async function getPayments(token: string, customerId?: number): Promise<Payment[]> {
  const params = new URLSearchParams();
  if (customerId) params.append("customer_id", String(customerId));

  const response = await fetch(`${API_URL}/api/payments?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<Payment[]>(response, "Could not load payments");
}

export async function reversePayment(token: string, paymentId: number, reversal_reason: string): Promise<Payment> {
  const response = await fetch(`${API_URL}/api/payments/${paymentId}/reverse`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ reversal_reason }),
  });
  return handleResponse<Payment>(response, "Failed to reverse payment");
}

// --- Reports APIs ---

export async function getMonthlyReview(token: string, billingMonth: string): Promise<MonthlyReviewData> {
  const response = await fetch(`${API_URL}/api/reports/monthly-review/${billingMonth}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<MonthlyReviewData>(response, "Could not load monthly review");
}

export async function getMonthlyRegister(
  token: string,
  billingMonth: string,
  area?: string,
  statusFilter?: string,
  search?: string,
): Promise<MonthlyRegisterResponse> {
  const params = new URLSearchParams();
  if (area) params.append("area", area);
  if (statusFilter) params.append("status_filter", statusFilter);
  if (search) params.append("search", search);

  const response = await fetch(`${API_URL}/api/reports/monthly-register/${billingMonth}?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<MonthlyRegisterResponse>(response, "Could not load monthly register");
}
