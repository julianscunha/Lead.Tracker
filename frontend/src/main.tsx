/**
 * lead_tracker — Frontend Entry Point (Fase 10)
 * ================================================
 * Contrato do Module Host: default export com render(container).
 * React/TypeScript compilado via Vite (lib mode, ESM único) — o Core só
 * serve .js estático, não compila .tsx (ver docs/fases/PROGRESSO.md).
 */
import { createRoot, type Root } from 'react-dom/client'
import { App } from './App'

export const moduleConfig = {
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

export default { render }
