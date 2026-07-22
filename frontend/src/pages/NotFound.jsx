import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/Logo";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-center px-6" data-testid="notfound-page">
      <Logo className="h-8 mb-8" />
      <div className="font-heading font-black text-7xl tracking-tight text-primary">404</div>
      <h1 className="font-heading font-bold text-2xl tracking-tight mt-2">Página não encontrada</h1>
      <p className="text-muted-foreground mt-2 max-w-sm">A página que procura não existe ou foi movida.</p>
      <Button asChild className="mt-6"><Link to="/" data-testid="back-home-button">Voltar ao Dashboard</Link></Button>
    </div>
  );
}
