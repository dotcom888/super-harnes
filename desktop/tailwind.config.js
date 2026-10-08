/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        harness: {
          bg: "#ffffff",
          sidebar: "#f9fafb",
          border: "#e5e7eb",
          hover: "#f3f4f6",
          active: "#e5e7eb",
          accent: "#2563eb",
          text: "#111827",
          muted: "#6b7280"
        }
      }
    }
  },
  plugins: []
}
