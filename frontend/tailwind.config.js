/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        critical: '#b91c1c',
        high: '#ea580c',
        medium: '#ca8a04',
        low: '#6b7280',
      },
    },
  },
  plugins: [],
}
