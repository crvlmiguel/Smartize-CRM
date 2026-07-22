import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, FolderKanban, FileText, Send, Server,
  BarChart3, Settings as SettingsIcon, ShieldCheck, LogOut, Mail,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/contactos", label: "Contactos", icon: Users },
  { to: "/grupos", label: "Grupos", icon: FolderKanban },
  { to: "/templates", label: "Templates", icon: FileText },
  { to: "/campanhas", label: "Campanhas", icon: Send },
  { to: "/smtp", label: "SMTP", icon: Server },
  { to: "/estatisticas", label: "Estatísticas", icon: BarChart3 },
  { to: "/deliverability", label: "Deliverability", icon: ShieldCheck },
  { to: "/configuracoes", label: "Configurações", icon: SettingsIcon },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-64 shrink-0 border-r border-border bg-card flex flex-col fixed h-screen">
        <div className="h-16 flex items-center gap-2 px-5 border-b border-border">
          <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center">
            <Mail size={18} className="text-primary-foreground" />
          </div>
          <div className="leading-tight">
            <div className="font-heading font-black text-sm tracking-tight">SMARTIZE</div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Outreach</div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <div className="px-2 py-2 mb-1">
            <div className="text-sm font-semibold truncate">{user?.name}</div>
            <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-button"
            className="flex w-full items-center gap-2 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors duration-150"
          >
            <LogOut size={16} /> Terminar sessão
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-64 min-h-screen">
        <div className="max-w-[1400px] mx-auto px-8 py-8 animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
