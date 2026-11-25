// Antes de las pruebas se vuelve a aplicar el escenario de DEMOSTRACIÓN flujo1: sus horas
// de verificación son relativas al momento de aplicarlo, así que reaplicarlo hace que los
// resultados (p. ej. "verificado hace 3 h") sean reproducibles.
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'

export default function preparacion() {
  const windows = process.platform === 'win32'
  const raiz = join(import.meta.dirname, '..', '..')
  const python = join(raiz, 'backend', '.venv', windows ? 'Scripts' : 'bin', windows ? 'python.exe' : 'python')
  execFileSync(python, [join(raiz, 'data', 'scripts', 'aplicar_escenario_demo.py'), 'flujo1'], {
    cwd: raiz,
    stdio: 'inherit',
  })
}
