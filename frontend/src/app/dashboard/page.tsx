import { ClientDashboard } from "@/components/client-dashboard";
import { RequireAuth } from "@/components/require-auth";

export default function DashboardPage() {
  return (
    <RequireAuth>
      <ClientDashboard />
    </RequireAuth>
  );
}
