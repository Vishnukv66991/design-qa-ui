const { spawn } = require('child_process');
const net = require('net');

const FIXED_PORT = 3000;

function isPortFree(port) {
  return new Promise((resolve) => {
    const tester = net.createServer()
      .once('error', () => resolve(false))
      .once('listening', () => tester.close(() => resolve(true)))
      .listen({ port, exclusive: true });
  });
}

async function start() {
  const port = Number(process.env.PORT || FIXED_PORT);

  const free = await isPortFree(port);
  if (!free) {
    console.error(`[Frontend] ERROR: Port ${port} is already in use.`);
    console.error(`[Frontend] Please free port ${port} before starting.`);
    console.error(`[Frontend] Run: netstat -ano | findstr :${port}  then  taskkill /f /pid <PID>`);
    process.exit(1);
  }

  console.log(`[Frontend] Starting on fixed port ${port}...`);

  const reactStartScript = require.resolve('react-scripts/scripts/start');
  const child = spawn(process.execPath, [reactStartScript], {
    stdio: 'inherit',
    env: { ...process.env, PORT: String(port) },
  });

  child.on('close', (code) => process.exit(code ?? 1));
}

start().catch((err) => {
  console.error('[Frontend] Failed to start:', err.message);
  process.exit(1);
});
