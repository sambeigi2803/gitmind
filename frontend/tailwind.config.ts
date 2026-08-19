import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "muted-foreground": "rgb(107 114 128)",
      },
    },
  },
  plugins: [],
};

export default config;
