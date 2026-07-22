import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Contacts from "@/pages/Contacts";
import Groups from "@/pages/Groups";
import Templates from "@/pages/Templates";
import Campaigns from "@/pages/Campaigns";
import CampaignDetail from "@/pages/CampaignDetail";
import Smtp from "@/pages/Smtp";
import Statistics from "@/pages/Statistics";
import Settings from "@/pages/Settings";
import Deliverability from "@/pages/Deliverability";
import NotFound from "@/pages/NotFound";
import { Logo } from "@/components/Logo";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <Logo className="h-8 animate-pulse" />
        <span className="text-muted-foreground text-sm">A carregar…</span>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <Protected>
                  <Layout />
                </Protected>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="contactos" element={<Contacts />} />
              <Route path="grupos" element={<Groups />} />
              <Route path="templates" element={<Templates />} />
              <Route path="campanhas" element={<Campaigns />} />
              <Route path="campanhas/:id" element={<CampaignDetail />} />
              <Route path="smtp" element={<Smtp />} />
              <Route path="estatisticas" element={<Statistics />} />
              <Route path="configuracoes" element={<Settings />} />
              <Route path="deliverability" element={<Deliverability />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
