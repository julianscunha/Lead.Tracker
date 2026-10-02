import { useState } from 'react'

const KEY = 'lt_rep_id'

function read(): string {
  try {
    return localStorage.getItem(KEY) ?? ''
  } catch {
    return '' // storage bloqueado (janela privada etc.): funciona sem lembrar
  }
}

/** Id do representante usado em todo o módulo (próxima ação, prospecção, conflitos, histórico).
 * Digitado uma vez só, no topo do App, e lembrado entre sessões. */
export function useRepId(): [string, (value: string) => void] {
  const [repId, setRepId] = useState(read)
  const update = (value: string) => {
    setRepId(value)
    try {
      localStorage.setItem(KEY, value)
    } catch {
      /* sem persistência: só vale nesta sessão */
    }
  }
  return [repId, update]
}
