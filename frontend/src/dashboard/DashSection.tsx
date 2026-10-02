import type { ReactNode } from 'react'

/** Bloco do dashboard organizado por pergunta do usuário ("o que fazer hoje?",
 * "como está o pipeline?"...) — região nomeada pra leitor de tela navegar. */
export function DashSection({ id, title, description, actions, children }: {
  id: string; title: string; description?: string; actions?: ReactNode; children: ReactNode
}) {
  return (
    <section className="lt-dash-section" aria-labelledby={`${id}-title`}>
      <div className="lt-dash-section__header">
        <div>
          <h3 id={`${id}-title`}>{title}</h3>
          {description && <p className="lt-hint">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}
