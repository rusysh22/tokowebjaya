/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Lexend", "sans-serif"],
      },
      colors: {
        neon: "#CAFF00",
        "neon-dark": "#B8E800",
        black: "#0A0A0A",
        "gray-950": "#0F0F0F",
        "gray-900": "#141414",
        "gray-800": "#1E1E1E",
        "gray-700": "#2A2A2A",
        "gray-600": "#3A3A3A",
        "gray-500": "#555555",
        "gray-400": "#888888",
        "gray-300": "#AAAAAA",
        "gray-200": "#CCCCCC",
        "gray-100": "#E0E0E0",
        "gray-50": "#F0F0F0",
        white: "#FFFFFF",
      },
      animation: {
        "fade-up": "fadeUp 0.6s ease forwards",
        "fade-in": "fadeIn 0.4s ease forwards",
        "slide-in-left": "slideInLeft 0.5s ease forwards",
        "slide-in-right": "slideInRight 0.5s ease forwards",
        "scale-in": "scaleIn 0.4s ease forwards",
        "float": "float 3s ease-in-out infinite",
        "shimmer": "shimmer 1.5s infinite",
        "spin-slow": "spin 8s linear infinite",
        "marquee": "marquee 30s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(24px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideInLeft: {
          "0%": { opacity: "0", transform: "translateX(-32px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        slideInRight: {
          "0%": { opacity: "0", transform: "translateX(32px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.92)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      transitionTimingFunction: {
        "smooth": "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
    require("@tailwindcss/forms"),
  ],
};
