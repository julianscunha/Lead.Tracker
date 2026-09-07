import { useEffect, useState } from 'react'
import {
  createProduct, createService, createVendor, listVendors,
  type Product, type Service, type Vendor,
} from '../api'

const NEW_VENDOR = '__new__'

// Achado da auditoria de dados: sem Salesforce não havia NENHUMA forma de
// cadastrar produto/serviço — só GET existia, o motor de regras (que exige
// categoria/item real do catálogo, nunca texto livre) ficava travado pra
// quem não sincroniza CRM nenhum. Esta tela fecha esse vazio.
//
// products/services vêm de SettingsScreen (estado elevado, compartilhado
// com RulesSection) — criar aqui avisa o pai via onProductCreated/
// onServiceCreated em vez de guardar cópia local, senão uma regra criada
// logo depois não veria a categoria nova sem recarregar a página.
export function PortfolioSection({
  products, services, loadError, onProductCreated, onServiceCreated,
}: {
  products: Product[] | null
  services: Service[] | null
  loadError: string | null
  onProductCreated: (p: Product) => void
  onServiceCreated: (s: Service) => void
}) {
  const [vendors, setVendors] = useState<Vendor[]>([])

  const [productFormOpen, setProductFormOpen] = useState(false)
  const [vendorChoice, setVendorChoice] = useState('')
  const [newVendorName, setNewVendorName] = useState('')
  const [productName, setProductName] = useState('')
  const [productCategory, setProductCategory] = useState('')
  const [savingProduct, setSavingProduct] = useState(false)
  const [productError, setProductError] = useState<string | null>(null)

  const [serviceFormOpen, setServiceFormOpen] = useState(false)
  const [serviceName, setServiceName] = useState('')
  const [serviceCategory, setServiceCategory] = useState('')
  const [savingService, setSavingService] = useState(false)
  const [serviceError, setServiceError] = useState<string | null>(null)

  const [vendorLoadError, setVendorLoadError] = useState<string | null>(null)

  useEffect(() => {
    listVendors()
      .then(setVendors)
      .catch(err => setVendorLoadError(err instanceof Error ? err.message : 'Não consegui carregar os fabricantes.'))
  }, [])

  const vendorName = (id: string) => vendors.find(v => v.id === id)?.name ?? id

  const resetProductForm = () => {
    setVendorChoice(''); setNewVendorName(''); setProductName(''); setProductCategory('')
  }

  const handleCreateProduct = async () => {
    setSavingProduct(true)
    setProductError(null)
    try {
      let vendorId = vendorChoice
      if (vendorChoice === NEW_VENDOR) {
        const vendor = await createVendor(newVendorName)
        setVendors(prev => [...prev, vendor])
        vendorId = vendor.id
      }
      const product = await createProduct(vendorId, productName, productCategory)
      onProductCreated(product)
      setProductFormOpen(false)
      resetProductForm()
    } catch (err) {
      setProductError(err instanceof Error ? err.message : 'Falha ao salvar produto.')
    } finally {
      setSavingProduct(false)
    }
  }

  const handleCreateService = async () => {
    setSavingService(true)
    setServiceError(null)
    try {
      const service = await createService(serviceName, serviceCategory)
      onServiceCreated(service)
      setServiceFormOpen(false)
      setServiceName(''); setServiceCategory('')
    } catch (err) {
      setServiceError(err instanceof Error ? err.message : 'Falha ao salvar serviço.')
    } finally {
      setSavingService(false)
    }
  }

  if (loadError || vendorLoadError) return <p className="lt-alert" role="alert">{loadError ?? vendorLoadError}</p>
  if (!products || !services) return <p className="lt-hint">Carregando portfólio…</p>

  const canSaveProduct = productName.trim() !== '' && (
    vendorChoice === NEW_VENDOR ? newVendorName.trim() !== '' : vendorChoice !== ''
  )
  const canSaveService = serviceName.trim() !== ''

  return (
    <div>
      <div className="lt-header">
        <h2>Portfólio</h2>
        <p>Produtos e serviços que sua empresa vende — é o catálogo que as Regras usam pra detectar oportunidade.</p>
      </div>

      <div className="lt-toolbar">
        <button type="button" className="lt-btn" onClick={() => setProductFormOpen(f => !f)}>
          {productFormOpen ? 'Cancelar' : 'Novo produto'}
        </button>
        <button type="button" className="lt-btn" onClick={() => setServiceFormOpen(f => !f)}>
          {serviceFormOpen ? 'Cancelar' : 'Novo serviço'}
        </button>
      </div>

      {productFormOpen && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Fabricante</span>
            <select value={vendorChoice} onChange={e => setVendorChoice(e.target.value)}>
              <option value="">Selecione…</option>
              {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
              <option value={NEW_VENDOR}>+ Cadastrar novo fabricante</option>
            </select>
          </label>
          {vendorChoice === NEW_VENDOR && (
            <label className="lt-field">
              <span>Nome do novo fabricante</span>
              <input value={newVendorName} onChange={e => setNewVendorName(e.target.value)} />
            </label>
          )}
          <label className="lt-field">
            <span>Nome do produto</span>
            <input value={productName} onChange={e => setProductName(e.target.value)} />
          </label>
          <label className="lt-field">
            <span>Categoria (ex.: backup, monitoramento — usada pelas Regras)</span>
            <input value={productCategory} onChange={e => setProductCategory(e.target.value)} />
          </label>
          {productError && <p className="lt-alert" role="alert">{productError}</p>}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleCreateProduct} disabled={savingProduct || !canSaveProduct}>
              {savingProduct ? 'Salvando…' : 'Criar produto'}
            </button>
          </div>
        </div>
      )}

      {serviceFormOpen && (
        <div className="lt-source-card__form">
          <label className="lt-field">
            <span>Nome do serviço</span>
            <input value={serviceName} onChange={e => setServiceName(e.target.value)} />
          </label>
          <label className="lt-field">
            <span>Categoria (ex.: backup, monitoramento — usada pelas Regras)</span>
            <input value={serviceCategory} onChange={e => setServiceCategory(e.target.value)} />
          </label>
          {serviceError && <p className="lt-alert" role="alert">{serviceError}</p>}
          <div className="lt-detail-actions">
            <button type="button" className="lt-btn" onClick={handleCreateService} disabled={savingService || !canSaveService}>
              {savingService ? 'Salvando…' : 'Criar serviço'}
            </button>
          </div>
        </div>
      )}

      {products.length === 0 ? (
        <p className="lt-empty" role="status">Nenhum produto cadastrado ainda.</p>
      ) : (
        <table className="lt-table">
          <thead>
            <tr><th>Fabricante</th><th>Produto</th><th>Categoria</th></tr>
          </thead>
          <tbody>
            {products.map(p => (
              <tr key={p.id}>
                <td>{vendorName(p.vendor_id)}</td>
                <td>{p.name}</td>
                <td>{p.category ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {services.length === 0 ? (
        <p className="lt-empty" role="status">Nenhum serviço cadastrado ainda.</p>
      ) : (
        <table className="lt-table">
          <thead>
            <tr><th>Serviço</th><th>Categoria</th></tr>
          </thead>
          <tbody>
            {services.map(s => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.category ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
