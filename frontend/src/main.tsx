/**
 * lead_tracker — Frontend Entry Point
 * ================================================
 * Contrato do Module Host: default export com render(container).
 * React/TypeScript compilado via Vite (lib mode, ESM único) — o Core só
 * serve .js estático, não compila .tsx.
 *
 * moduleConfig fica aninhado no default export (não como export nomeado
 * separado) de propósito: ModuleHost.tsx só lê mod.default.render em
 * runtime, nunca importa moduleConfig — e com dois exports nomeados
 * (default + moduleConfig), o Rollup consolida tudo num único
 * `export { x as default, y }` no fim do bundle, sem a substring literal
 * "export default" que o validador oficial (`techforge validate-module`)
 * procura via busca textual. Com um export só, o Rollup emite
 * `export default X` de verdade — mesmo dado, sem o falso-positivo.
 */
import { createRoot, type Root } from 'react-dom/client'
import { App } from './App'

const moduleConfig = {
  moduleId: 'lead_tracker',
  title: 'Lead.Tracker',
  icon: 'target',
  category: 'Sales',
  vendor: 'TechForge',
  route: '/modules/lead_tracker',
  description: 'Opportunity Intelligence — tela de oportunidades.',
}

let root: Root | null = null

function render(container: HTMLElement) {
  root = createRoot(container)
  root.render(<App />)
}

export default { render, moduleConfig }
