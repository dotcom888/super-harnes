const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const BACKEND_PORT = 8765;

function checkBackendReady(callback) {
  const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/status`, (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else {
      callback(false);
    }
  });
  req.on('error', () => callback(false));
  req.end();
}

function resolvePythonCommand() {
  const venvWin = path.resolve(__dirname, '../../.venv/Scripts/python.exe');
  const venvUnix = path.resolve(__dirname, '../../.venv/bin/python');
  if (process.platform === 'win32' && fs.existsSync(venvWin)) {
    return venvWin;
  }
  if (process.platform !== 'win32' && fs.existsSync(venvUnix)) {
    return venvUnix;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startBackendDaemon() {
  checkBackendReady((isReady) => {
    if (isReady) {
      console.log('Super-Harnes backend is already running on port', BACKEND_PORT);
      return;
    }

    console.log('Spawning Super-Harnes backend daemon...');
    const pythonCmd = resolvePythonCommand();
    const serverScript = path.resolve(__dirname, '../../server/run_server.py');

    pythonProcess = spawn(pythonCmd, [serverScript, String(BACKEND_PORT)], {
      cwd: path.resolve(__dirname, '../..'),
      stdio: 'inherit',
      env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    pythonProcess.on('error', (err) => {
      console.error('Failed to spawn Python backend:', err);
    });
  });
}

function createWindow() {
  const iconPath = path.join(__dirname, '../public/logo.png');

  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 1024,
    minHeight: 700,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#ffffff',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const devUrl = 'http://localhost:5173';
  const prodPath = path.join(__dirname, '../dist/index.html');

  const testReq = http.get(devUrl, () => {
    mainWindow.loadURL(devUrl);
  });
  testReq.on('error', () => {
    mainWindow.loadFile(prodPath);
  });

  ipcMain.on('window-minimize', () => mainWindow?.minimize());
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on('window-close', () => mainWindow?.close());

  // 文件夹选择对话框 (支持选择磁盘项目作为新工作区)
  ipcMain.handle('dialog:select-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '选择本地项目作为工作区',
      properties: ['openDirectory', 'createDirectory']
    });
    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });
}

app.whenReady().then(() => {
  startBackendDaemon();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('Terminating Python backend daemon...');
    try {
      pythonProcess.kill();
    } catch (e) {}
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
