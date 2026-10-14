"use client";

export function ProgressRing({ value, size = 72 }: { value: number; size?: number }) {
  const clamped = Math.max(0, Math.min(1, value));
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  return (
    <svg width={size} height={size} role="img" aria-label={`掌握度 ${Math.round(clamped * 100)}%`}>
      <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e5e7eb" strokeWidth={6} fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        stroke="#3b82f6"
        strokeWidth={6}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="53%" textAnchor="middle" fontSize={14} fill="#111827">
        {Math.round(clamped * 100)}%
      </text>
    </svg>
  );
}
