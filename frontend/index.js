/**
 * lead_tracker — Frontend Entry Point
 * ======================================================
 * Esqueleto do módulo (Fase 04). Micro-frontend puro (sem framework) —
 * o Module Host só exige um default export com render(container).
 * Sem UI de negócio ainda: só confirma que o módulo abre.
 */

export const moduleConfig = {
  moduleId: 'lead_tracker',
  title: 'Lead.Tracker',
  icon: 'target',
  category: 'Sales',
  vendor: 'Tech.Forge',
  route: '/modules/lead_tracker',
  description: 'Opportunity Intelligence — esqueleto do módulo.',
}

function render(container) {
  container.innerHTML = ''
  container.style.cssText = 'padding:32px;font-family:inherit;'

  const title = document.createElement('h2')
  title.textContent = 'Lead.Tracker'
  title.style.cssText = 'font-size:15px;font-weight:600;color:hsl(var(--text));margin:0 0 4px;'

  const subtitle = document.createElement('p')
  subtitle.textContent = 'Esqueleto do módulo — Fase 04. Sem funcionalidade de negócio ainda.'
  subtitle.style.cssText = 'font-size:11px;color:hsl(var(--text-muted));margin:0;'

  container.appendChild(title)
  container.appendChild(subtitle)
}

export default { render }
