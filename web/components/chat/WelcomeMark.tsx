"use client";

/** A soft geometric "M" mark for the chat welcome area. */
export function WelcomeMark({ size = 72 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="MasteryPath"
      className="opacity-25"
    >
      <defs>
        <linearGradient id="mp-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.9" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.4" />
        </linearGradient>
      </defs>
      <path
        d="M8 52V14l12 18 12-18 12 18 12-18v38"
        fill="none"
        stroke="url(#mp-mark)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
