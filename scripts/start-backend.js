/**
 * Cross-platform backend starter.
 * Finds uvicorn INSIDE the venv (no manual activation needed).
 * Works on Windows, Mac, and Linux.
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const backendDir = path.join(__dirname, '..', 'backend');
const isWindows = process.platform === 'win32';
const CTRL_C_EXIT_CODE = 3221225786; // 0xC000013A on Windows

// Find uvicorn inside the venv — no need to "activate" anything
const uvicornPath = isWindows
  ? path.join(backendDir, 'venv', 'Scripts', 'uvicorn.exe')
  : path.join(backendDir, 'venv', 'bin', 'uvicorn');

if (!fs.existsSync(uvicornPath)) {
  console.error('\n[Backend] ❌ uvicorn not found at:', uvicornPath);
  console.error('[Backend] Run "npm install" first — it will set up the Python backend automatically.\n');
  process.exit(1);
}

console.log('[Backend] Starting FastAPI server...');

const uvicorn = spawn(uvicornPath, ['main:app', '--reload', '--port', '8000'], {
  cwd: backendDir,
  stdio: 'inherit',
});

function shutdown(signal) {
  if (!uvicorn.killed) {
    uvicorn.kill(signal);
  }
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

uvicorn.on('error', (err) => {
  console.error('\n[Backend] Failed to start uvicorn:', err.message);
  console.error('[Backend] Run "npm install" first to set up the backend.\n');
});

uvicorn.on('close', (code) => {
  if (code === 0 || code === CTRL_C_EXIT_CODE) {
    process.exit(0);
    return;
  }

  if (code !== 0) {
    console.error(`[Backend] uvicorn exited with code ${code}`);
  }

  process.exit(code ?? 1);
});
