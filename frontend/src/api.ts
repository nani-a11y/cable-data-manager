const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
