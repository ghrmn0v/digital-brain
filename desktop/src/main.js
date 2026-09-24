import { app, BrowserWindow } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function createWindow() {
  const win = new BrowserWindow({
    width: 960,
    height: 680,
    title: "Fly / Connectome",
    backgroundColor: "#0b0f14",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "index.html"));
  if (process.env.FLY_OPEN_DEVTOOLS === "1") {
    win.webContents.openDevTools();
  }
  if (process.env.FLY_SMOKE === "1") {
    win.webContents.on("console-message", (_event, level, message) => {
      console.log(`[renderer:${level}] ${message}`);
    });
    win.webContents.on("did-finish-load", () => {
      setTimeout(() => {
        console.log("FLY_SMOKE_OK");
        app.exit(0);
      }, 2000);
    });
    win.webContents.on("render-process-gone", (_event, details) => {
      console.error("FLY_SMOKE_CRASH", details.reason);
      app.exit(1);
    });
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});