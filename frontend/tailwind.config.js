/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f2f6fb",
          100: "#e2ebf5",
          200: "#c3d4e8",
          300: "#94b3d6",
          400: "#5d8abd",
          500: "#3a6ba5",
          600: "#2c5489",
          700: "#25446e",
          800: "#1e3554",
          900: "#17293f",
          950: "#0f1c2e",
        },
        teal: {
          50: "#effcfa",
          100: "#c9f4ef",
          200: "#96e8df",
          300: "#5cd5c8",
          400: "#2fbcae",
          500: "#149c8d",
          600: "#0e7d72",
          700: "#0e645c",
          800: "#0f504a",
          900: "#10423e",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto",
               "Helvetica Neue", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(16 32 54 / 0.06), 0 1px 3px 0 rgb(16 32 54 / 0.10)",
      },
    },
  },
  plugins: [],
};
