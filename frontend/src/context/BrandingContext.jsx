import { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";

const BrandingContext = createContext({ logo_url: "/smartize-logo.webp", company_name: "Smartize", refresh: () => {} });
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState({ logo_url: "/smartize-logo.webp", company_name: "Smartize" });

  const refresh = useCallback(() => {
    axios.get(`${API}/public/branding`)
      .then((r) => setBranding({ logo_url: r.data.logo_url || "/smartize-logo.webp", company_name: r.data.company_name || "Smartize" }))
      .catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <BrandingContext.Provider value={{ ...branding, refresh }}>
      {children}
    </BrandingContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
