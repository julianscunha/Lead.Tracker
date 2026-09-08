import { useEffect, useRef, useState } from 'react'

// Achado do usuário: cards com explicação sempre visível (um parágrafo
// abaixo do título) poluem a tela — vira um botão "(i)" no canto do
// cabeçalho, clicável (não só hover, pra funcionar por teclado/toque),
// que abre um popover pequeno com o mesmo texto.
export function InfoHint({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onClickOutside)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="lt-info-hint" ref={ref}>
      <button
        type="button"
        className="lt-info-hint__btn"
        aria-label="Mais informações"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        i
      </button>
      {open && <div className="lt-info-hint__popover" role="tooltip">{text}</div>}
    </div>
  )
}
