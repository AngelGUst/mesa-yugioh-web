#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkbox, confirm } from '@inquirer/prompts';
import chalk from 'chalk';
import figlet from 'figlet';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const IS_WIN = process.platform === 'win32';
const REQUIRED = 'backend';
const children = [];

const SERVICES = {
  backend: {
    label: 'backend - API FastAPI (:8000)',
    dir: 'backend',
    command: 'python',
    args: ['-m', 'uvicorn', 'main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'],
    color: 'cyan',
    required: true,
  },
  frontend: {
    label: 'frontend - SvelteKit (:5173)',
    dir: 'frontend',
    command: 'npm',
    args: ['run', 'dev', '--', '--host', '0.0.0.0', '--port', '5173'],
    color: 'green',
  },
};

function banner() {
  let art;
  try {
    art = figlet.textSync('DUEL', { font: 'ANSI Shadow' });
  } catch {
    art = 'DUEL';
  }
  console.log(chalk.red(art));
  console.log(chalk.bold('  Panel de arranque de Duel Assistant\n'));
}

function paintFor(color) {
  return chalk[color] ?? chalk.white;
}

function spawnProcess(command, args, options = {}) {
  return spawn(command, args, {
    shell: IS_WIN,
    windowsHide: IS_WIN,
    ...options,
  });
}

function prefixChunk(prefix, chunk) {
  return chunk
    .toString()
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .map((line, index, lines) => index === lines.length - 1 && line === '' ? '' : `${prefix} ${line}`)
    .filter(Boolean)
    .join('\n')
    .concat('\n');
}

function runOnce(command, args, cwd, tag) {
  return new Promise((resolve) => {
    console.log(chalk.gray(`  -> ${tag}`));
    const process = spawnProcess(command, args, { cwd, stdio: 'inherit' });
    process.on('exit', () => resolve());
    process.on('error', (error) => {
      console.log(chalk.red(`  x ${tag}: ${error.message}`));
      resolve();
    });
  });
}

function launchService(key) {
  const service = SERVICES[key];
  const prefix = paintFor(service.color)(`[${key}]`);
  const child = spawnProcess(service.command, service.args, { cwd: join(ROOT, service.dir) });
  child.stdout.on('data', (data) => process.stdout.write(prefixChunk(prefix, data)));
  child.stderr.on('data', (data) => process.stderr.write(prefixChunk(prefix, data)));
  child.on('exit', (code) => console.log(`${prefix} ${chalk.yellow(`terminado (${code ?? 'sin codigo'})`)}`));
  child.on('error', (error) => console.log(`${prefix} ${chalk.red(error.message)}`));
  children.push(child);
  console.log(`${prefix} ${chalk.green('iniciado')}`);
}

function killChild(child) {
  if (!child.pid || child.killed) return;
  if (IS_WIN) {
    spawnProcess('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
  } else {
    child.kill('SIGINT');
  }
}

function shutdown() {
  console.log(chalk.yellow('\nApagando Duel Assistant...'));
  for (const child of children) killChild(child);
  setTimeout(() => process.exit(0), 500);
}

function printPlan(toStart, withDatabase) {
  console.log(chalk.bold('\nPlan de arranque:'));
  for (const key of toStart) {
    const exists = existsSync(join(ROOT, SERVICES[key].dir));
    const mark = exists ? chalk.green('ok') : chalk.red('x carpeta no existe');
    const required = SERVICES[key].required ? chalk.yellow(' [obligatorio]') : '';
    console.log(`  ${mark} ${key}${required}`);
  }
  console.log(`  ${withDatabase ? chalk.green('ok') : chalk.gray('-')} PostgreSQL (Docker)`);
}

async function main() {
  banner();
  const dry = process.argv.includes('--dry');
  const requiredChoice = {
    name: `${SERVICES[REQUIRED].label} ${chalk.yellow('[obligatorio]')}`,
    value: REQUIRED,
    checked: true,
    disabled: chalk.dim('siempre activo'),
  };
  const optionalChoices = Object.entries(SERVICES)
    .filter(([key]) => key !== REQUIRED)
    .map(([key, service]) => ({ name: service.label, value: key, checked: true }));

  let selected;
  let withDatabase;
  if (dry) {
    selected = Object.keys(SERVICES);
    withDatabase = true;
  } else {
    selected = await checkbox({
      message: 'Servicios a levantar (espacio = marcar, enter = confirmar):',
      choices: [requiredChoice, ...optionalChoices],
    });
    withDatabase = await confirm({
      message: 'Levantar PostgreSQL con Docker?',
      default: true,
    });
  }

  const toStart = Array.from(new Set([...selected, REQUIRED]));
  printPlan(toStart, withDatabase);
  if (dry) {
    console.log(chalk.gray('\n(--dry) No se lanza nada. Solo se muestra el plan.'));
    return;
  }

  if (withDatabase) {
    await runOnce('docker', ['compose', 'up', '-d', 'postgres'], ROOT, 'docker compose up -d postgres');
  }

  console.log('');
  for (const key of toStart) {
    if (!existsSync(join(ROOT, SERVICES[key].dir))) {
      console.log(chalk.red(`  x ${key}: no existe la carpeta "${SERVICES[key].dir}".`));
      continue;
    }
    launchService(key);
  }

  if (children.length === 0) {
    console.log(chalk.yellow('\nNo se levanto ningun servicio.'));
    return;
  }
  console.log(chalk.gray('\nPresiona Ctrl+C para apagar todo.\n'));
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((error) => {
  if (error?.name === 'ExitPromptError') {
    console.log(chalk.gray('\nCancelado.'));
    process.exit(0);
  }
  console.error(chalk.red(error));
  process.exit(1);
});
