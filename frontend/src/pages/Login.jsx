import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import { Logo } from "@/components/Logo";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Sessão iniciada");
      navigate("/");
    } catch (err) {
      toast.error(apiError(err, "Credenciais inválidas"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative">
        <img
          src="https://images.pexels.com/photos/16615599/pexels-photo-16615599.jpeg?auto=compress&cs=tinysrgb&w=1200"
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-primary/20" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <h2 className="font-heading font-black text-4xl tracking-tight drop-shadow">
            Email Outreach profissional.
          </h2>
          <p className="mt-2 text-white/90 max-w-md">
            Campanhas outbound simples, organizadas e com elevada taxa de entrega.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 bg-background">
        <form onSubmit={submit} className="w-full max-w-sm" data-testid="login-form">
          <div className="flex items-center gap-2 mb-8">
            <Logo className="h-8" />
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground mt-1.5">Outreach</span>
          </div>
          <h1 className="font-heading font-black text-2xl tracking-tight mb-1">Bem-vindo de volta</h1>
          <p className="text-sm text-muted-foreground mb-6">Inicie sessão para continuar.</p>

          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email" type="email" value={email} required
                data-testid="login-email-input"
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nome@smartize.pt" className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password" type="password" value={password} required
                data-testid="login-password-input"
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••" className="mt-1.5"
              />
            </div>
            <Button type="submit" disabled={loading} data-testid="login-submit-button" className="w-full">
              {loading && <Loader2 size={16} className="mr-2 animate-spin" />}
              Entrar
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
