import { useEffect, useState } from "react";
import {
  Plus, CheckCircle, AlertCircle, Users
} from "lucide-react";
import { AreaItem, getServiceAreas, addServiceArea, renameServiceArea, archiveServiceArea } from "./api";

type Props = {
  token: string;
};

export default function AreasView({ token }: Props) {
  const [areas, setAreas] = useState<AreaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [newAreaName, setNewAreaName] = useState("");
  const [adding, setAdding] = useState(false);

  // Rename state
  const [renameTarget, setRenameTarget] = useState<AreaItem | null>(null);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState(false);

  const loadAreas = async () => {
    setLoading(true);
    try {
      const data = await getServiceAreas(token, true);
      setAreas(data);
    } catch (err: any) {
      setError(err.message || "Could not load areas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAreas();
  }, [token]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAreaName.trim()) return;
    setAdding(true);
    setError("");
    setSuccess("");
    try {
      const res = await addServiceArea(token, newAreaName.trim());
      setSuccess(res.message);
      setNewAreaName("");
      loadAreas();
    } catch (err: any) {
      setError(err.message || "Could not add area");
    } finally {
      setAdding(false);
    }
  };

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renameTarget || !newName.trim()) return;
    setRenaming(true);
    setError("");
    setSuccess("");
    try {
      const res = await renameServiceArea(token, renameTarget.name, newName.trim());
      setSuccess(`${res.message} (${res.updated_customers} customer records updated).`);
      setRenameTarget(null);
      setNewName("");
      loadAreas();
    } catch (err: any) {
      setError(err.message || "Could not rename area");
    } finally {
      setRenaming(false);
    }
  };

  const handleArchiveToggle = async (area: AreaItem) => {
    const action = area.is_active ? "archive" : "activate";
    if (!window.confirm(`Are you sure you want to ${action} service area "${area.name}"?`)) return;

    setError("");
    setSuccess("");
    try {
      const res = await archiveServiceArea(token, area.name, !area.is_active);
      setSuccess(res.message);
      loadAreas();
    } catch (err: any) {
      setError(err.message || "Failed to update area status");
    }
  };

  return (
    <div className="content">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">CONFIGURATION</p>
          <h1>Service Areas</h1>
          <p className="muted">Manage neighborhood cable distribution zones and active coverage.</p>
        </div>
      </div>

      {error && <div className="notice" style={{ borderColor: "#ef4444" }}><AlertCircle size={18} color="#ef4444"/><div><strong>Error</strong><p>{error}</p></div></div>}
      {success && <div className="notice" style={{ borderColor: "#16a34a" }}><CheckCircle size={18} color="#16a34a"/><div><strong>Success</strong><p>{success}</p></div></div>}

      <div className="panel" style={{ padding: 20, marginBottom: 24 }}>
        <h3 style={{ marginBottom: 12 }}>Add New Service Area</h3>
        <form onSubmit={handleAdd} style={{ display: "flex", gap: 12, maxWidth: 500 }}>
          <input
            type="text"
            required
            placeholder="e.g. Sector 5, Old Bazaar, North Colony"
            value={newAreaName}
            onChange={(e) => setNewAreaName(e.target.value)}
            style={{ flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}
          />
          <button type="submit" disabled={adding} className="primary-btn" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Plus size={16} /> {adding ? "Adding..." : "Add Area"}
          </button>
        </form>
      </div>

      <div className="panel" style={{ padding: 0, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
              <th style={{ padding: "12px 16px" }}>Area Name</th>
              <th style={{ padding: "12px 16px" }}>Subscribers</th>
              <th style={{ padding: "12px 16px" }}>Status</th>
              <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} style={{ padding: 32, textAlign: "center", color: "#64748b" }}>Loading areas...</td></tr>
            ) : areas.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: 32, textAlign: "center", color: "#64748b" }}>No service areas configured.</td></tr>
            ) : (
              areas.map((a) => (
                <tr key={a.name} style={{ borderBottom: "1px solid #f1f5f9", background: a.is_active ? "transparent" : "#f8fafc" }}>
                  <td style={{ padding: "12px 16px", fontWeight: 600 }}>{a.name}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#64748b" }}>
                      <Users size={15} /> {a.customer_count} customers
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{
                      padding: "2px 8px", borderRadius: 12, fontSize: 12, fontWeight: 500,
                      background: a.is_active ? "#dcfce7" : "#fee2e2",
                      color: a.is_active ? "#15803d" : "#b91c1c"
                    }}>
                      {a.is_active ? "Active" : "Archived"}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      onClick={() => { setRenameTarget(a); setNewName(a.name); }}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#0284c7", marginRight: 12, fontSize: 13, fontWeight: 500 }}
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => handleArchiveToggle(a)}
                      style={{ background: "none", border: "none", cursor: "pointer", color: a.is_active ? "#d97706" : "#16a34a", fontSize: 13, fontWeight: 500 }}
                    >
                      {a.is_active ? "Archive" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Rename Modal */}
      {renameTarget && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, padding: 16
        }}>
          <div style={{ background: "#fff", borderRadius: 12, width: "100%", maxWidth: 450, padding: 24, boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1)" }}>
            <h2 style={{ marginBottom: 8 }}>Rename Service Area</h2>
            <p className="muted" style={{ marginBottom: 16 }}>
              Renaming "{renameTarget.name}" will automatically update all {renameTarget.customer_count} associated customer records.
            </p>

            <form onSubmit={handleRename}>
              <input
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1", marginBottom: 20 }}
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                <button type="button" onClick={() => setRenameTarget(null)} className="secondary-btn">Cancel</button>
                <button type="submit" disabled={renaming} className="primary-btn">{renaming ? "Updating..." : "Save Rename"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
