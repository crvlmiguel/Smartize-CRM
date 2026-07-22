export function Logo({ className = "h-7", white = false }) {
  return (
    <img
      src="/smartize-logo.webp"
      alt="Smartize"
      className={className}
      style={white ? { filter: "brightness(0) invert(1)" } : undefined}
    />
  );
}
