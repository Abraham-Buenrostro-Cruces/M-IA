// Regenera src/api/esquema.d.ts a partir del OpenAPI de api-core (FastAPI). Uso: npm run api:tipos
//
// openapi-typescript se ejecuta con npx en su propio entorno porque exige TypeScript 5
// como dependencia par y el proyecto usa TypeScript 7. Se invoca npx-cli.js con el mismo
// Node (no npx.cmd): en Windows, Node no permite lanzar .cmd sin shell.
import { execFileSync } from 'node:child_process'
import { dirname, join } from 'node:path'

const windows = process.platform === 'win32'
const python = join('..', 'backend', '.venv', windows ? 'Scripts' : 'bin', windows ? 'python.exe' : 'python')
const npxCli = join(dirname(process.env.npm_execpath ?? ''), 'npx-cli.js')

execFileSync(python, ['-m', 'app.exportar_openapi', join('..', 'frontend', 'src', 'api', 'openapi.json')], {
  stdio: 'inherit',
  cwd: join('..', 'backend'),
})
execFileSync(process.execPath, [npxCli, '--yes', 'openapi-typescript@7', 'src/api/openapi.json', '-o', 'src/api/esquema.d.ts'], {
  stdio: 'inherit',
})
