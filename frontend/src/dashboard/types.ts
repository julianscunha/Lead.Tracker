// Espelha core/dashboard_metrics.py FUNNEL_STAGES — mantido em sincronia manual.
export const FUNNEL_STAGES = ['Detectadas', 'Qualificadas', 'Abordadas', 'Em negociação']

// Espelha core/dashboard_metrics.py::FUNNEL_REACH_ORDER — 5 estágios (inclui
// "reviewed", que FUNNEL_STAGES/funnel_counts não têm). Rótulo em português
// só aqui; a chave em inglês (funnel_reach.stage) nunca muda de nome —
// decisão do Pipeline Analyst pra nunca confundir com "conversion".
export const FUNNEL_REACH_LABELS: Record<string, string> = {
  detected: 'Detectadas', qualified: 'Qualificadas', reviewed: 'Revisadas',
  contacted: 'Abordadas', opportunity: 'Em negociação',
}
