// Antes de las pruebas se reaplica el escenario de DEMOSTRACIÓN flujo1 y se borran los
// reportes de la comunidad: sus horas de verificación son relativas al momento de
// aplicarlo, así que los resultados (p. ej. "verificado hace 3 h") son reproducibles.
// También se crea el moderador de desarrollo y su token queda en RA_TOKEN_MODERADOR.
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'

const windows = process.platform === 'win32'
const raiz = join(import.meta.dirname, '..', '..')
const python = join(raiz, 'backend', '.venv', windows ? 'Scripts' : 'bin', windows ? 'python.exe' : 'python')

function script(nombre: string, ...args: string[]): string {
  return execFileSync(python, [join(raiz, 'data', 'scripts', nombre), ...args], {
    cwd: raiz,
    encoding: 'utf-8',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  }).trim()
}

/** Deja la base como al inicio de la demo (se usa también entre pruebas de reportes).
 *
 *  El script escribe directo en la base; luego se pide al backend que recalcule a través
 *  de su bus, para que invalide su caché de estados (si no, durante hasta 60 s la siguiente
 *  prueba vería los estados de la anterior). */
export async function reiniciarDemo() {
  script('aplicar_escenario_demo.py', 'flujo1', '--reiniciar')
  const r = await fetch('http://127.0.0.1:8000/operacion/recalcular-estados', {
    method: 'POST',
    headers: { Authorization: `Bearer ${process.env.RA_TOKEN_MODERADOR}` },
  })
  if (!r.ok) throw new Error(`No se pudo recalcular estados: ${r.status}`)
}

export default async function preparacion() {
  process.env.RA_TOKEN_MODERADOR = script('crear_moderador_dev.py')
  await reiniciarDemo()
}
