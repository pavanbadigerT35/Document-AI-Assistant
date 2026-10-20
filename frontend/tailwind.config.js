/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Public Sans Variable"', "system-ui", "Segoe UI", "sans-serif"],
        serif: ['"Newsreader Variable"', "Georgia", "serif"],
      },
      colors: {
        ink: { DEFAULT: "#17232E", soft: "#4A5866", faint: "#6B7885" },
        rail: { DEFAULT: "#12303A", hover: "#1B4352", line: "#2A5666" },
        page: "#F2F5F7",
        line: "#D5DDE3",
        signal: { DEFAULT: "#0B6E6A", dark: "#08524F", tint: "#E3F2F1" },
        pass: "#1E7B4F",
        fail: "#B3261E",
        work: "#1D5FA8",
        mark: "#FFE58A",
      },
    },
  },
  plugins: [],
};
