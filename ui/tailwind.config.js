/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0B10",
        panel: "#0F1117", 
        ink: "#E5E7EB",
        sub: "#9CA3AF",
        aqua: "#22d3ee",
        grape: "#a78bfa", 
        citrus: "#f59e0b",
        punch: "#f43f5e",
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem'
      },
      boxShadow: {
        'soft': '0 8px 40px rgba(0,0,0,0.35)',
        'glow': '0 0 0 1px rgba(255,255,255,0.05), 0 10px 50px rgba(163, 230, 53, 0.15)'
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' }
        }
      },
      animation: {
        'shimmer': 'shimmer 2s linear infinite'
      }
    }
  },
  plugins: []
}
