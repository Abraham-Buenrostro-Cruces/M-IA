export function Inicio() {
  return (
    <>
      <h1 className="text-3xl font-bold text-marca-oscuro">
        Viaja por la CDMX sin barreras
      </h1>
      <p className="mt-4 text-lg">
        RutaAccesible te propone rutas en Metro, Metrobús y Tren Ligero que priorizan
        llegar sin obstáculos: elevadores que funcionan, rampas y transbordos accesibles.
        El tiempo de viaje es secundario.
      </p>
      <section aria-labelledby="titulo-como-funciona" className="mt-8">
        <h2 id="titulo-como-funciona" className="text-xl font-semibold">
          Cómo funciona
        </h2>
        <ul className="mt-3 list-disc space-y-2 pl-6">
          <li>Eliges tu perfil de movilidad; se guarda sólo en tu dispositivo.</li>
          <li>
            Cada ruta muestra su Índice de Accesibilidad de Ruta (IAR), los equipos críticos
            y cuándo se verificaron por última vez.
          </li>
          <li>Si no hay una ruta segura, te lo decimos claramente.</li>
        </ul>
      </section>
      <p className="mt-8 rounded border border-gray-300 bg-gray-50 p-4 text-texto-suave">
        Versión en desarrollo: la planificación de rutas aún no está disponible.
      </p>
    </>
  )
}
