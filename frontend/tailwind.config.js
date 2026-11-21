/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "#F8FAFC",
          surface: "#FFFFFF",
          subtle: "#F1F5F9",
          inset: "#E2E8F0",
          border: "#E2E8F0",
          strong: "#CBD5E1",
        },
        ink: {
          primary: "#0F172A",
          secondary: "#475569",
          muted: "#64748B",
        },
        risk: {
          fg: "#991B1B",
          bg: "#FEF2F2",
          border: "#FECACA",
          dot: "#DC2626",
        },
        warn: {
          fg: "#92400E",
          bg: "#FFFBEB",
          border: "#FDE68A",
          dot: "#D97706",
        },
        ok: {
          fg: "#065F46",
          bg: "#ECFDF5",
          border: "#A7F3D0",
          dot: "#059669",
        },
        brand: {
          50: "#ECFDF5",
          100: "#D1FAE5",
          600: "#059669",
          700: "#047857",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
