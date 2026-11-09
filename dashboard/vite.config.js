import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    globals: true,
    // Partage un seul environnement jsdom entre fichiers de test plutôt que
    // d'en recréer un par fichier (c'était 82% du temps d'exécution avant
    // ce réglage, Vitest le recommande lui-même dans son résumé de run).
    isolate: false,
  },
})
