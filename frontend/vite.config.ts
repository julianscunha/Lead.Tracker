import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Contrato de módulo Tech.Forge: o Core só serve .js/.mjs estático, sem
// compilar nada — precisa sair daqui já como um único ESM (bundle,
// sem code-splitting, sem CSS externo: injetado via <style> no próprio JS).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '.',
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: 'src/main.tsx',
      formats: ['es'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
})
