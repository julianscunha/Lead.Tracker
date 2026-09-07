import { useEffect, useState } from 'react'

function isDark(): boolean {
  return document.documentElement.classList.contains('theme-dark') || document.body.classList.contains('theme-dark')
}

/** O Core alterna `.theme-dark` num ancestral (ver styles.ts) — sem observar
 * isso, os gráficos ficam presos na paleta validada só pro fundo claro
 * (references/palette.md da skill dataviz), que reprova contraste/banda de
 * luminosidade no fundo escuro (validado com validate_palette.js --mode dark). */
export function useIsDarkTheme(): boolean {
  const [dark, setDark] = useState(isDark)
  useEffect(() => {
    const observer = new MutationObserver(() => setDark(isDark()))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return dark
}
