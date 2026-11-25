// Foto saneada de un reporte. La API exige identidad, así que se descarga como blob y se
// muestra con una URL de objeto local (que se libera al desmontar).
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/cliente'

export function FotoEvidencia({ id, moderacion = false, alt }: { id: string; moderacion?: boolean; alt: string }) {
  const { data: url, isPending, isError } = useQuery({
    queryKey: ['evidencia', id, moderacion],
    queryFn: () => api.evidencia(id, moderacion),
    retry: 2, // la versión saneada aparece unos segundos después de enviar el reporte
    staleTime: Infinity,
  })
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url)
  }, [url])
  if (isPending) return <p className="text-sm text-texto-suave">Cargando foto…</p>
  if (isError) return <p className="text-sm text-texto-suave">La foto aún no está disponible.</p>
  return <img src={url} alt={alt} className="max-h-72 rounded border border-gray-300" />
}
