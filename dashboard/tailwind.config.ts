import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#1F4E79", dark: "#143659", light: "#D6E4F5" },
        amber: "#F2B84B",
      },
    },
  },
  plugins: [],
} satisfies Config;
