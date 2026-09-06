// Usa só os tokens de tema já definidos pelo Core (hsl(var(--...))) —
// sem cor inventada, sem gradiente, sem roxo padrão de IA.
export const styles = `
.lt-root { padding: 24px; font-family: inherit; color: hsl(var(--text)); }
.lt-header { margin-bottom: 16px; }
.lt-header h2 { font-size: 15px; font-weight: 600; margin: 0 0 4px; }
.lt-header p { font-size: 11px; color: hsl(var(--text-muted)); margin: 0; }

.lt-filters { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.lt-filters label { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: hsl(var(--text-muted)); }
.lt-filters select, .lt-filters input {
  font-size: 12px; padding: 6px 8px; border-radius: 6px;
  border: 1px solid hsl(var(--border)); background: hsl(var(--bg)); color: hsl(var(--text));
}

.lt-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.lt-table th { text-align: left; padding: 8px; border-bottom: 1px solid hsl(var(--border)); color: hsl(var(--text-muted)); font-weight: 500; }
.lt-table th button {
  all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
}
.lt-table th button:focus-visible { outline: 2px solid hsl(var(--accent)); outline-offset: 2px; }
.lt-table td { padding: 8px; border-bottom: 1px solid hsl(var(--border-subtle)); vertical-align: top; }
.lt-table tbody tr:hover { background: hsl(var(--bg-subtle)); }

.lt-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 600; }
.lt-badge--customer { background: hsl(var(--success) / 0.15); color: hsl(var(--success)); }
.lt-badge--prospect { background: hsl(var(--bg-subtle)); color: hsl(var(--text-muted)); border: 1px solid hsl(var(--border)); }
.lt-badge--severity-baixo { background: hsl(var(--success) / 0.15); color: hsl(var(--success)); }
.lt-badge--severity-medio { background: hsl(var(--warning) / 0.15); color: hsl(var(--warning)); }
.lt-badge--severity-alto { background: hsl(var(--warning) / 0.25); color: hsl(var(--warning)); }
.lt-badge--severity-critico { background: hsl(var(--danger) / 0.15); color: hsl(var(--danger)); }
.lt-badge--severity-nao_avaliado { background: hsl(var(--bg-subtle)); color: hsl(var(--text-muted)); border: 1px solid hsl(var(--border)); }
.lt-badge--health-verde { background: hsl(var(--success) / 0.15); color: hsl(var(--success)); }
.lt-badge--health-amarela { background: hsl(var(--warning) / 0.15); color: hsl(var(--warning)); }
.lt-badge--health-vermelha { background: hsl(var(--danger) / 0.15); color: hsl(var(--danger)); }
.lt-badge--health-dados_insuficientes { background: hsl(var(--bg-subtle)); color: hsl(var(--text-muted)); border: 1px solid hsl(var(--border)); }
.lt-badge--discovery-promoted { background: hsl(var(--success) / 0.15); color: hsl(var(--success)); }
.lt-badge--discovery-deferred { background: hsl(var(--warning) / 0.15); color: hsl(var(--warning)); }
.lt-badge--discovery-rejected { background: hsl(var(--bg-subtle)); color: hsl(var(--text-muted)); border: 1px solid hsl(var(--border)); }

.lt-severity { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; margin-bottom: 12px; }
.lt-severity label { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: hsl(var(--text-muted)); }
.lt-severity select, .lt-severity textarea {
  font-size: 12px; padding: 6px 8px; border-radius: 6px;
  border: 1px solid hsl(var(--border)); background: hsl(var(--bg)); color: hsl(var(--text));
}
.lt-severity textarea { min-width: 220px; min-height: 32px; resize: vertical; font-family: inherit; }

.lt-expand-btn { all: unset; cursor: pointer; padding: 4px; border-radius: 4px; }
.lt-expand-btn:focus-visible { outline: 2px solid hsl(var(--accent)); outline-offset: 2px; }

.lt-detail { background: hsl(var(--bg-elevated)); padding: 12px 16px; }
.lt-detail dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 0 0 12px; }
.lt-detail dt { color: hsl(var(--text-muted)); }
.lt-detail dd { margin: 0; }
.lt-detail-actions { display: flex; gap: 8px; }
.lt-btn {
  font-size: 11px; padding: 6px 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid hsl(var(--border)); background: hsl(var(--bg)); color: hsl(var(--text));
}
.lt-btn:hover { background: hsl(var(--bg-subtle)); }
.lt-btn:focus-visible { outline: 2px solid hsl(var(--accent)); outline-offset: 2px; }
.lt-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.lt-hint { font-size: 10px; color: hsl(var(--text-muted)); margin-top: 6px; }

.lt-draft { margin-top: 12px; padding: 12px; border-radius: 6px; background: hsl(var(--bg)); border: 1px solid hsl(var(--border)); font-size: 11px; }
.lt-draft p { margin: 0 0 8px; }

.lt-toolbar { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 12px; }

.lt-empty { text-align: center; padding: 48px 16px; color: hsl(var(--text-muted)); font-size: 12px; }

.lt-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid hsl(var(--border)); }
.lt-tab {
  all: unset; cursor: pointer; padding: 8px 12px; font-size: 12px; color: hsl(var(--text-muted));
  border-bottom: 2px solid transparent;
}
.lt-tab[aria-selected="true"] { color: hsl(var(--text)); border-bottom-color: hsl(var(--accent)); font-weight: 600; }
.lt-tab:focus-visible { outline: 2px solid hsl(var(--accent)); outline-offset: 2px; }

.lt-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 20px; }
.lt-stat-tile { border: 1px solid hsl(var(--border-subtle)); border-radius: 8px; padding: 12px; background: hsl(var(--bg-elevated)); }
.lt-stat-tile__value { font-size: 18px; font-weight: 600; color: hsl(var(--text)); }
.lt-stat-tile__label { font-size: 10px; color: hsl(var(--text-muted)); margin-top: 2px; }

.lt-chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
.lt-chart-card { border: 1px solid hsl(var(--border-subtle)); border-radius: 8px; padding: 16px; background: hsl(var(--bg-elevated)); }
.lt-chart-card h3 { font-size: 12px; font-weight: 600; margin: 0 0 12px; color: hsl(var(--text)); }
.lt-chart-card--wide { grid-column: 1 / -1; }

.lt-source-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.lt-source-card { border: 1px solid hsl(var(--border-subtle)); border-radius: 8px; padding: 16px; background: hsl(var(--bg-elevated)); }
.lt-source-card__header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.lt-source-card__title { font-size: 13px; font-weight: 600; margin: 0; color: hsl(var(--text)); }
.lt-source-card__status { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.lt-conn-indicator { font-size: 11px; color: hsl(var(--text-muted)); white-space: nowrap; }
.lt-toggle { display: flex; align-items: center; gap: 6px; font-size: 11px; cursor: pointer; }
.lt-source-card__form { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.lt-field { display: flex; flex-direction: column; gap: 4px; font-size: 11px; }
.lt-field span:first-child { font-weight: 600; color: hsl(var(--text)); }
.lt-field input { font-size: 12px; padding: 6px 8px; border-radius: 6px; border: 1px solid hsl(var(--border)); background: hsl(var(--bg)); color: hsl(var(--text)); }
`
