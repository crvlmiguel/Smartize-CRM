import { useBranding } from "@/context/BrandingContext";

export function Logo({ className = "h-7", white = false }) {
  const { logo_url } = useBranding();
  return (
    <img
      src={logo_url || "/smartize-logo.webp"}
      alt="Smartize"
      className={`${className} w-auto object-contain`}
      style={white ? { filter: "brightness(0) invert(1)" } : undefined}
    />
  );
}
