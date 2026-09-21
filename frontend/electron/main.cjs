const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");

const isDev = !app.isPackaged;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    title: "Morpheus — Digital Forensics",
  });

  if (isDev) {
    win.loadURL("http://localhost:5173");
    // win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

/**
 * Native file picker — returns full absolute path(s).
 * Renderer calls window.electronAPI.openFile(...)
 */
ipcMain.handle("dialog:openFile", async (_event, options = {}) => {
  const result = await dialog.showOpenDialog({
    title: options.title || "Select evidence file",
    properties: options.properties || ["openFile"],
    filters: options.filters || [
      {
        name: "Disk images",
        extensions: ["e01", "E01", "ex01", "Ex01", "dd", "raw", "img", "vmdk", "vhd", "vhdx", "aff", "001"],
      },
      { name: "All files", extensions: ["*"] },
    ],
  });

  if (result.canceled || !result.filePaths?.length) {
    return null;
  }
  // Full absolute path(s) — this is what the backend needs
  return result.filePaths.length === 1 ? result.filePaths[0] : result.filePaths;
});
