import { useEffect, useState, type ReactNode } from 'react'
import { listProducts, listServices, listSettings, type Product, type Service, type SourceStatus } from '../api'
import { InfoHint } from '../InfoHint'
import { AiConfigSection } from './AiConfigSection'
import { summarizeSync } from './DataInputScreen'
import { FieldMappingSection } from './FieldMappingSection'
import { PortfolioSection } from './PortfolioSection'
import { RepTargetsSection } from './RepTargetsSection'
import { RulesSection } from './RulesSection'
import { ThresholdsSection } from './ThresholdsSection'

// Mantido aqui por compatibilidade com quem importava de SettingsScreen.
export { summarizeSync }

function Fold({ title, open, children }: { title: string; open?: boolean; children: ReactNode }) {
  return (
    <details className="lt-fold" open={open}>
      <summary>{title}</summary>
      <div className="lt-fold__body">{children}</div>
    </details>
  )
}

// Calibragem (uso raro): o que você vende, as regras que detectam oportunidade, a IA e os limites.
// Entrada de dado fica na aba "Entrada de dados"; conflitos entre fontes, em "Oportunidades".
export function SettingsScreen() {
  const [sources, setSources] = useState<SourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Catálogo (produtos/serviços) elevado pra cá — Portfólio cria e Regras consome; se cada seção buscasse
  // por conta própria, um produto criado em Portfólio só apareceria em Regras depois de recarregar a página.
  const [products, setProducts] = useState<Product[] | null>(null)
  const [services, setServices] = useState<Service[] | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  const reloadCatalog = () => {
    Promise.all([listProducts(), listServices()])
      .then(([p, s]) => { setProducts(p); setServices(s) })
      .catch(err => setCatalogError(err instanceof Error ? err.message : 'Não consegui carregar o portfólio.'))
  }

  useEffect(() => {
    listSettings()
      .then(setSources)
      .catch(err => setError(err instanceof Error ? err.message : 'Não consegui carregar as configurações.'))
    reloadCatalog()
  }, [])

  if (error) return <p className="lt-alert" role="alert">{error}</p>
  if (!sources) return <p className="lt-hint">Carregando...</p>

  const salesforceOn = sources.find(s => s.id === 'salesforce')?.enabled

  return (
    <div>
      <div className="lt-header lt-header-row">
        <h2>Configurações</h2>
        <InfoHint text="Calibragem do sistema, de uso mais raro: o que você vende (portfólio), as regras que detectam oportunidades, a IA e os limites. Conectar fontes e atualizar dados fica em Entrada de dados." />
      </div>

      <Fold title="Portfólio — o que você vende" open>
        <PortfolioSection
          products={products} services={services} loadError={catalogError}
          onProductCreated={p => setProducts(prev => [...(prev ?? []), p])}
          onServiceCreated={s => setServices(prev => [...(prev ?? []), s])}
          onProductDeleted={id => setProducts(prev => (prev ?? []).filter(p => p.id !== id))}
          onServiceDeleted={id => setServices(prev => (prev ?? []).filter(s => s.id !== id))}
          onCatalogChanged={reloadCatalog}
        />
      </Fold>
      <Fold title="Regras de correlação — quando há uma oportunidade">
        <RulesSection products={products ?? []} services={services ?? []} />
      </Fold>
      {salesforceOn && (
        <Fold title="Mapeamento de campos do Salesforce">
          <FieldMappingSection />
        </Fold>
      )}
      <Fold title="Inteligência artificial">
        <AiConfigSection />
      </Fold>
      <Fold title="Limites e prazos (triagem, cota diária, promoção)">
        <ThresholdsSection />
      </Fold>
      <Fold title="Metas por representante">
        <RepTargetsSection />
      </Fold>
    </div>
  )
}
