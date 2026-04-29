/**
 * Automatic backend setup script.
 * Runs after `npm install` (via postinstall hook).
 *
 * 1. Creates a Python venv inside backend/ if it doesn't exist
 * 2. Installs all pip dependencies from requirements.txt
 *
 * Requires: Python 3.9+ installed on the system.
 */
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const backendDir = path.join(__dirname, '..', 'backend');
const venvDir = path.join(backendDir, 'venv');
const isWindows = process.platform === 'win32';
const pip = isWindows
  ? path.join(venvDir, 'Scripts', 'pip.exe')
  : path.join(venvDir, 'bin', 'pip');

function run(cmd, label) {
  console.log(`\n[setup-backend] ${label}...`);
  try {
    execSync(cmd, { cwd: backendDir, stdio: 'inherit' });
  } catch (err) {
    console.error(`[setup-backend] ❌ Failed: ${label}`);
    console.error(`[setup-backend] Command: ${cmd}`);
    console.error(`[setup-backend] Make sure Python 3.9+ is installed and available as "python" or "python3".`);
    process.exit(1);
  }
}

// ── Step 1: Create venv if it doesn't exist ──
if (!fs.existsSync(pip)) {
  // Try "python" first, fall back to "python3" (Linux/Mac)
  const pythonCmd = (() => {
    try {
      execSync('python --version', { stdio: 'pipe' });
      return 'python';
    } catch {
      try {
        execSync('python3 --version', { stdio: 'pipe' });
        return 'python3';
      } catch {
        console.error('[setup-backend] ❌ Python not found. Please install Python 3.9+ and try again.');
        process.exit(1);
      }
    }
  })();

  run(`${pythonCmd} -m venv venv`, 'Creating Python virtual environment');
} else {
  console.log('\n[setup-backend] ✅ Python venv already exists');
}

// ── Step 2: Install pip dependencies ──
const reqFile = path.join(backendDir, 'requirements.txt');
if (fs.existsSync(reqFile)) {
  const pipCmd = isWindows
    ? `"${pip}" install -r requirements.txt`
    : `"${pip}" install -r requirements.txt`;
  run(pipCmd, 'Installing Python dependencies');
}

console.log('\n[setup-backend] ✅ Backend setup complete!\n');
