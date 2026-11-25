import { Link } from 'react-router'

export function NoEncontrada() {
  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">Página no encontrada</h1>
      <p className="mt-4">
        <Link to="/" className="text-marca underline">
          Volver al inicio
        </Link>
      </p>
    </>
  )
}
