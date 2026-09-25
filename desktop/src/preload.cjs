const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("flyApi", {
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
  },
});