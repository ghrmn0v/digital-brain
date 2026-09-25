const { app, BrowserWindow } = require("electron");
const path = require("path");

app.on("window-all-closed", () => app.quit());

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: 960,
    height: 680,
    show: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "src", "preload.cjs"),
      backgroundThrottling: false,
    },
  });
  win.webContents.on("console-message", (_e, level, message) => {
    console.log(`[r:${level}] ${message}`);
  });
  await win.loadFile(path.join(__dirname, "src", "index.html"));
  await new Promise((r) => setTimeout(r, 2500));
  await win.webContents.executeJavaScript(`localStorage.setItem("fly.debug", "1"); location.reload(); true`);
  await new Promise((r) => setTimeout(r, 4000));

  const trigger = async (body) => {
    const res = await win.webContents.executeJavaScript(
      `fetch("http://127.0.0.1:8080/api/v1/events", {
         method: "POST", headers: {"Content-Type": "application/json"},
         body: JSON.stringify(${JSON.stringify(body)}),
       }).then(r => r.json()).then(d => d.fetch)`,
    );
    console.log(`[event] ${body.event}@${body.priority} -> ${res}`);
    await new Promise((r) => setTimeout(r, 6000));
  };

  await trigger({ event: "process_completed", source: "demo", priority: 0.8, context: { topic: "build" } });
  await trigger({ event: "warning", source: "demo", priority: 0.95, context: { topic: "system", body_preview: "Disk 90%", sender_name: "Demo" } });
  await trigger({ event: "important_message", source: "demo", priority: 0.9, context: { topic: "job", body_preview: "CTO görüş təsdiqləndi", sender_name: "Demo" } });
  await trigger({ event: "process_failed", source: "demo", priority: 0.8, context: { topic: "build" } });

  app.exit(0);
});