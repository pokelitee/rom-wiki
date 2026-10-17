// A game cartridge: the ROM every page is decoded from. Its label window and
// insertion arrow are cut out of the body so the mark reads on any background.
// public/favicon.svg draws the same shape on the brand tile.
const LOGO_PATH =
  "M7 2.5h8.5L19 6v13.5a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-15a2 2 0 0 1 2-2Z" +
  "M8.5 5.5a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1Z" +
  "M9.25 8h5.5v1.4h-5.5ZM9.25 10.6h3.5V12h-3.5Z" +
  "M12 15.6l2.6 3.2H9.4Z";

export function Logo({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      fillRule="evenodd"
      aria-hidden="true"
    >
      <path d={LOGO_PATH} />
    </svg>
  );
}
