const { execSync } = require('child_process');
const http = require('http');

const isWindows = process.platform === 'win32';
const FRONTEND_PORT = Number(process.env.PORT || 3000);
const BACKEND_PORT = Number(process.env.BACKEND_PORT || 8000);
const ports = [FRONTEND_PORT, BACKEND_PORT];

function checkBackendHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: '127.0.0.1', port, path: '/', timeout: 1200 },
      (res) => {
        resolve(res.statusCode >= 200 && res.statusCode < 500);
      }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function run(command) {
  return execSync(command, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  });
}

function pidsOnWindows(port) {
  const output = run(`netstat -ano -p tcp`);
  const pids = new Set();

  output
    .split(/\r?\n/)
    .forEach((line) => {
      if (line.includes(`:${port}`) && line.includes('LISTENING')) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (/^\d+$/.test(pid) && pid !== '0') {
          pids.add(pid);
        }
      }
    });

  return [...pids];
}

function pidsOnUnix(port) {
  const output = run(`lsof -ti tcp:${port}`);
  const pids = new Set(
    output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => /^\d+$/.test(line))
  );

  return [...pids];
}

async function main() {
  for (const port of ports) {
    try {
      const pids = isWindows ? pidsOnWindows(port) : pidsOnUnix(port);
      if (pids.length > 0) {
        console.log(`[Startup] Port ${port} appears in use by PID(s): ${pids.join(', ')}. Attempting to free...`);
        for (const pid of pids) {
          try {
            run(`taskkill /f /pid ${pid}`);
            console.log(`[Startup] Killed PID ${pid}`);
          } catch (_) {
            // Process may have already exited
          }
        }
        // Wait a moment for the port to be released
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (_) {
      // No process was using this port.
    }
  }
}

main();
