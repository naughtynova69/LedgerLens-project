/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "#090D16",
          subtle: "#0D1322",
          surface: "#111827",
          elevated: "#162032",
          border: "#1F293D",
          borderHighlight: "#2D3B55",
        },
        brand: {
          50: "#ECFDF5",
          100: "#D1FAE5",
          400: "#34D399",
          500: "#10B981",
          600: "#059669",
        },
        severity: {
          critical: "#F43F5E",
          high: "#F59E0B",
          medium: "#38BDF8",
          low: "#94A3B8",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Inter",
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
      boxShadow: {
        glow: "0 0 25px -5px rgba(16, 185, 129, 0.15)",
        glowCritical: "0 0 25px -5px rgba(244, 63, 94, 0.2)",
      },
    },
  },
  plugins: [],
};
