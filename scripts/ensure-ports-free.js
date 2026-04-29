const { execSync } = require('child_process');

const isWindows = process.platform === 'win32';
const ports = [3000, 8000];

function run(command) {
  return execSync(command, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  });
}

function killOnWindows(port) {
  const output = run(`netstat -ano -p tcp | findstr :${port}`);
  const pids = new Set();

  output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const parts = line.split(/\s+/);
      const pid = parts[parts.length - 1];
      if (/^\d+$/.test(pid)) {
        pids.add(pid);
      }
    });

  pids.forEach((pid) => {
    try {
      execSync(`taskkill /PID ${pid} /F`, { stdio: 'ignore' });
      console.log(`[Startup] Freed port ${port} by stopping PID ${pid}.`);
    } catch (_) {
      // Process may have already exited.
    }
  });
}

function killOnUnix(port) {
  const output = run(`lsof -ti tcp:${port}`);
  const pids = new Set(
    output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => /^\d+$/.test(line))
  );

  pids.forEach((pid) => {
    try {
      execSync(`kill -9 ${pid}`, { stdio: 'ignore' });
      console.log(`[Startup] Freed port ${port} by stopping PID ${pid}.`);
    } catch (_) {
      // Process may have already exited.
    }
  });
}

for (const port of ports) {
  try {
    if (isWindows) {
      killOnWindows(port);
    } else {
      killOnUnix(port);
    }
  } catch (_) {
    // No process was using this port.
  }
}
