import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Rollup sempre emite `export { x as default }` no modo lib deste build,
// nunca a substring literal `export default` — e o validador oficial do
// Tech.Forge (`techforge validate-module`) checa essa substring via busca
// textual ingênua. `rollupOptions.output.banner` deveria resolver isso mas
// o Vite (5.4.21) não o aplica no modo lib — via generateBundle direto no
// bundle final, então.
function exportDefaultBannerPlugin(): Plugin {
  return {
    name: 'export-default-banner',
    generateBundle(_options, bundle) {
      for (const file of Object.values(bundle)) {
        if (file.type === 'chunk' && file.isEntry) {
          file.code = `// Tech.Forge Module Host contract: this bundle's \`export default\` is the render() entry point.\n${file.code}`
        }
      }
    },
  }
}

// Contrato de módulo Tech.Forge: o Core só serve .js/.mjs estático, sem
// compilar nada — precisa sair daqui já como um único ESM (bundle,
// sem code-splitting, sem CSS externo: injetado via <style> no próprio JS).
export default defineConfig({
  plugins: [react(), exportDefaultBannerPlugin()],
  // O bundle é importado diretamente pelo navegador, sem o polyfill de
  // `process` do Node. React ainda usa esta expressão nos builds CommonJS;
  // substituí-la na compilação impede `process is not defined` em runtime.
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
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
        // Rollup sempre emite `export { x as default }` neste modo de build,
        // nunca a substring literal `export default` — e o validador oficial
        // do Tech.Forge (`techforge validate-module`) checa essa substring
        // via busca textual ingênua. Banner sobrevive à minificação (é
        // inserido depois) e documenta o contrato de verdade, então dobra
        // como o texto que o validador procura.
        banner: '// Tech.Forge Module Host contract: this bundle\'s `export default` is the render() entry point.',
      },
    },
  },
})
