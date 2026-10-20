/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Public Sans Variable"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ['"Newsreader Variable"', "Georgia", "serif"],
      },
      colors: {
        ink: { DEFAULT: "#212121", soft: "#616161", faint: "#75758A" },
        rail: { DEFAULT: "#003C33", hover: "#0C4B40", line: "#30665B" },
        page: "#FFFFFF",
        line: "#D9D9DD",
        signal: { DEFAULT: "#17171C", dark: "#003C33", tint: "#EDFCE9" },
        "soft-stone": "#EEECE7",
        "pale-green": "#EDFCE9",
        "pale-blue": "#F1F5FF",
        "focus-blue": "#4C6EE6",
        pass: "#276749",
        fail: "#B30000",
        work: "#1863DC",
        mark: "#FFF0B3",
      },
    },
  },
  plugins: [],
};
