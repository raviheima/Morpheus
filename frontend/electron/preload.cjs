const { contextBridge, ipcRenderer } = require("electron");

/**
 * Safe API exposed to the renderer.
 * No Node APIs leak into the page.
 */
contextBridge.exposeInMainWorld("electronAPI", {
  /**
   * Open native file dialog and return full absolute path (or null if cancelled).
   * @param {object} [options]
   * @param {string} [options.title]
   * @param {string[]} [options.properties] e.g. ["openFile", "multiSelections"]
   * @param {{ name: string, extensions: string[] }[]} [options.filters]
   * @returns {Promise<string|string[]|null>}
   */
  openFile: (options) => ipcRenderer.invoke("dialog:openFile", options),

  /** True when running inside Electron */
  isElectron: true,
});
