import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        accent: "var(--accent)",
        border: "var(--border)",
        ring: "var(--ring)",
        popover: "var(--popover)",
        destructive: "var(--destructive)",
      },
      borderRadius: { xl: "0.75rem" },
    },
  },
  plugins: [],
};

export default config;
