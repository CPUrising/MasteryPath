"use client";

export function ProgressRing({
  value,
  size = 20,
  stroke = 2,
  showLabel = true,
}: {
  value: number;
  size?: number;
  stroke?: number;
  showLabel?: boolean;
}) {
  const clamped = Math.max(0, Math.min(1, value));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <svg width={size} height={size} role="img" aria-label={`${Math.round(clamped * 100)}%`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--primary)"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - clamped)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      {showLabel && (
        <text x="50%" y="54%" textAnchor="middle" fontSize={size * 0.3} fill="var(--foreground)">
          {Math.round(clamped * 100)}%
        </text>
      )}
    </svg>
  );
}
