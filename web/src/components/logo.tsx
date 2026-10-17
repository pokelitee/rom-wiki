// A game cartridge: the ROM every page is decoded from. public/favicon.svg
// draws the same shape.
export function Logo({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 3h10.5L19 6.5V21H5z" />
      <rect x="8" y="6.5" width="8" height="6" rx="1" />
      <path d="M8.5 16.5v2M12 16.5v2M15.5 16.5v2" />
    </svg>
  );
}
