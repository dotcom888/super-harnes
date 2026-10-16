const { app, BrowserWindow, ipcMain, dialog, shell, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const BACKEND_PORT = 8765;
const terminalSessions = new Map();

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

function getBundledServerExe() {
  const exeName = process.platform === 'win32' ? 'super-server.exe' : 'super-server';
  const packagedPath = path.join(process.resourcesPath, 'bin', 'super-server', exeName);
  if (fs.existsSync(packagedPath)) {
    return packagedPath;
  }
  const devPath = path.resolve(__dirname, '../bin/super-server', exeName);
  if (fs.existsSync(devPath)) {
    return devPath;
  }
  return null;
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

    const bundledExe = getBundledServerExe();
    if (bundledExe) {
      console.log('Spawning bundled standalone backend engine:', bundledExe);
      try {
        pythonProcess = spawn(bundledExe, [String(BACKEND_PORT)], {
          cwd: path.dirname(bundledExe),
          stdio: 'inherit',
          windowsHide: true,
          env: { ...process.env, PYTHONUNBUFFERED: '1' }
        });

        pythonProcess.on('error', (err) => {
          console.error('Failed to spawn bundled backend:', err);
        });

        pythonProcess.on('exit', (code, signal) => {
          console.log(`Bundled backend exited with code ${code}, signal ${signal}`);
        });
        return;
      } catch (err) {
        console.error('Error launching bundled backend:', err);
      }
    }

    console.log('Falling back to system/venv python...');
    const pythonCmd = resolvePythonCommand();
    let serverScript = path.resolve(__dirname, '../../backend/server/run_server.py');
    if (!fs.existsSync(serverScript)) {
      serverScript = path.resolve(__dirname, '../../server/run_server.py');
    }

    if (fs.existsSync(serverScript)) {
      pythonProcess = spawn(pythonCmd, [serverScript, String(BACKEND_PORT)], {
        cwd: path.resolve(__dirname, '../..'),
        stdio: 'inherit',
        windowsHide: true,
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
      });

      pythonProcess.on('error', (err) => {
        console.error('Failed to spawn Python backend:', err);
      });
    } else {
      console.error('Neither bundled backend nor server script found!');
    }
  });
}

function killAllTerminals() {
  for (const [id, proc] of terminalSessions.entries()) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t']);
      } else {
        proc.kill('SIGTERM');
      }
    } catch (e) {}
  }
  terminalSessions.clear();
}

function killBackend() {
  killAllTerminals();
  if (pythonProcess) {
    console.log('Terminating backend daemon...');
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t']);
      } else {
        pythonProcess.kill('SIGTERM');
      }
    } catch (e) {}
    pythonProcess = null;
  }
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
      contextIsolation: true,
      webviewTag: true
    }
  });

  const prodPath = path.join(__dirname, '../dist/index.html');
  const devUrl = process.env.VITE_DEV_SERVER_URL || null;

  if (app.isPackaged || (!devUrl && fs.existsSync(prodPath))) {
    mainWindow.loadFile(prodPath);
  } else if (devUrl) {
    mainWindow.loadURL(devUrl);
  } else {
    const testReq = http.get('http://localhost:5173', () => {
      mainWindow.loadURL('http://localhost:5173');
    });
    testReq.on('error', () => {
      mainWindow.loadFile(prodPath);
    });
  }

  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i')) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  
  // 读取系统剪贴板中的真实文件 (针对 Windows 资源管理器 Ctrl+C 复制的文件) 或截图图片
  ipcMain.handle('clipboard:read-media', async () => {
    const result = { files: [], image: null };
    try {
      // 1. 检查 Windows 资源管理器复制的文件 (CF_HDROP / FileNameW)
      if (process.platform === 'win32') {
        const buf = clipboard.readBuffer('FileNameW');
        if (buf && buf.length > 0) {
          const rawStr = buf.toString('ucs2');
          const paths = rawStr.split('\0').filter((p) => p.length > 0 && fs.existsSync(p));
          for (const filePath of paths) {
            try {
              const stat = fs.statSync(filePath);
              if (stat.isFile() && stat.size <= 50 * 1024 * 1024) {
                const fileBuf = fs.readFileSync(filePath);
                result.files.push({
                  name: path.basename(filePath),
                  path: filePath,
                  size: stat.size,
                  dataBase64: fileBuf.toString('base64')
                });
              }
            } catch (e) {}
          }
        }
      }

      // 2. 检查系统剪贴板中的截图或复制的图片
      if (result.files.length === 0) {
        const img = clipboard.readImage();
        if (!img.isEmpty()) {
          const pngBuf = img.toPNG();
          result.image = {
            name: `screenshot_${Date.now()}.png`,
            size: pngBuf.length,
            dataBase64: pngBuf.toString('base64')
          };
        }
      }
    } catch (err) {
      console.error('Error reading clipboard media in main:', err);
    }
    return result;
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

  // 外部浏览器打开 URL
  ipcMain.on('shell:open-external', (_event, url) => {
    if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
      shell.openExternal(url);
    }
  });

  // 文件夹选择对话框
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

  // 终端会话 IPC 处理 (用于右侧调试侧边栏运行 PowerShell / 终端)
  ipcMain.handle('terminal:create', (event, { id, cwd }) => {
    if (terminalSessions.has(id)) {
      return { success: true, cwd: cwd || path.resolve(__dirname, '../..') };
    }
    const shellCmd = process.platform === 'win32' ? 'powershell.exe' : (process.env.SHELL || 'bash');
    const shellArgs = process.platform === 'win32' ? ['-NoLogo', '-ExecutionPolicy', 'Bypass'] : [];
    const targetCwd = cwd || path.resolve(__dirname, '../..');

    try {
      const proc = spawn(shellCmd, shellArgs, {
        cwd: targetCwd,
        env: { ...process.env, TERM: 'xterm-256color' },
        windowsHide: true
      });

      proc.stdout.on('data', (data) => {
        event.sender.send(`terminal:data:${id}`, data.toString('utf8'));
      });

      proc.stderr.on('data', (data) => {
        event.sender.send(`terminal:data:${id}`, data.toString('utf8'));
      });

      proc.on('exit', (code) => {
        event.sender.send(`terminal:exit:${id}`, code);
        terminalSessions.delete(id);
      });

      terminalSessions.set(id, proc);
      return { success: true, cwd: targetCwd };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.on('terminal:write', (event, { id, data, cwd }) => {
    let proc = terminalSessions.get(id);
    if (!proc) {
      const shellCmd = process.platform === 'win32' ? 'powershell.exe' : (process.env.SHELL || 'bash');
      const shellArgs = process.platform === 'win32' ? ['-NoLogo', '-ExecutionPolicy', 'Bypass'] : [];
      const targetCwd = cwd || path.resolve(__dirname, '../..');
      try {
        proc = spawn(shellCmd, shellArgs, {
          cwd: targetCwd,
          env: { ...process.env, TERM: 'xterm-256color' },
          windowsHide: true
        });
        proc.stdout.on('data', (d) => event.sender.send(`terminal:data:${id}`, d.toString('utf8')));
        proc.stderr.on('data', (d) => event.sender.send(`terminal:data:${id}`, d.toString('utf8')));
        proc.on('exit', (code) => {
          event.sender.send(`terminal:exit:${id}`, code);
          terminalSessions.delete(id);
        });
        terminalSessions.set(id, proc);
      } catch (e) {
        console.error('Failed to auto-spawn terminal in write:', e);
      }
    }
    if (proc && proc.stdin && proc.stdin.writable) {
      proc.stdin.write(data);
    }
  });

  ipcMain.on('terminal:kill', (_event, { id }) => {
    const proc = terminalSessions.get(id);
    if (proc) {
      try {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t']);
        } else {
          proc.kill('SIGTERM');
        }
      } catch (e) {}
      terminalSessions.delete(id);
    }
  });
}

app.whenReady().then(() => {
  startBackendDaemon();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('will-quit', killBackend);
app.on('before-quit', killBackend);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
