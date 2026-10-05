const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("bookalyzer", {
  call: (method, params) => ipcRenderer.invoke("analysis", method, params),
  pickFiles: () => ipcRenderer.invoke("pick-files"),
  exportLibrary: () => ipcRenderer.invoke("library-export"),
  pickLibrary: () => ipcRenderer.invoke("library-pick"),
  save: (name, content, format) =>
    ipcRenderer.invoke("save-report", { name, content, format }),
});
