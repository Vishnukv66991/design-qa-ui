/**
 * Cross-platform backend starter.
 * Finds uvicorn INSIDE the venv (no manual activation needed).
 * Works on Windows, Mac, and Linux.
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const net = require('net');
const http = require('http');

const backendDir = path.join(__dirname, '..', 'backend');
const isWindows = process.platform === 'win32';
const CTRL_C_EXIT_CODE = 3221225786; // 0xC000013A on Windows
const backendPort = process.env.BACKEND_PORT || '8000';

function isPortFree(port) {
  return new Promise((resolve) => {
    const tester = net.createServer()
      .once('error', () => resolve(false))
      .once('listening', () => tester.close(() => resolve(true)))
      .listen({ port: Number(port), exclusive: true });
  });
}

function isBackendHealthy(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: '127.0.0.1', port: Number(port), path: '/', timeout: 1200 },
      (res) => resolve(res.statusCode >= 200 && res.statusCode < 500)
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

// Find uvicorn inside the venv — no need to "activate" anything
const uvicornPath = isWindows
  ? path.join(backendDir, 'venv', 'Scripts', 'uvicorn.exe')
  : path.join(backendDir, 'venv', 'bin', 'uvicorn');

if (!fs.existsSync(uvicornPath)) {
  console.error('\n[Backend] ❌ uvicorn not found at:', uvicornPath);
  console.error('[Backend] Run "npm install" first — it will set up the Python backend automatically.\n');
  process.exit(1);
}

async function start() {
  const free = await isPortFree(backendPort);
  if (!free) {
    const healthy = await isBackendHealthy(backendPort);
    if (healthy) {
      console.log(`[Backend] Existing backend detected on port ${backendPort}; reusing it.`);
      process.exit(0);
      return;
    }
    console.error(`[Backend] Port ${backendPort} is already in use by another process.`);
    process.exit(1);
    return;
  }

  console.log(`[Backend] Starting FastAPI server on port ${backendPort}...`);

  const uvicorn = spawn(uvicornPath, ['main:app', '--reload', '--port', backendPort], {
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
}

start().catch((err) => {
  console.error('[Backend] Unexpected startup failure:', err.message);
  process.exit(1);
});
