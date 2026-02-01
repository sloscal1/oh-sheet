/**
 * Browser abstraction layer.
 *
 * Wraps browser-specific extension APIs behind a portable interface so that
 * the rest of the codebase never calls chrome.* / browser.* directly.
 *
 * Current implementation: Chrome (Manifest V3).
 * To port to Firefox or Safari, swap the function bodies below.
 */

const BrowserAPI = {
  /**
   * Send a message from content script / popup to the service worker.
   * @param {object} message - Message payload (must include a `type` field).
   * @returns {Promise<any>} Response from the service worker.
   */
  sendMessage(message) {
    return chrome.runtime.sendMessage(message);
  },

  /**
   * Register a message listener (used in the service worker).
   * The handler receives (message, sender) and must return a value or a
   * Promise.  Returning `undefined` means "no response".
   *
   * @param {function(object, object): (any|Promise<any>)} handler
   */
  onMessage(handler) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      const result = handler(message, sender);
      if (result instanceof Promise) {
        result.then(sendResponse).catch((err) => {
          sendResponse({ error: err.message || String(err) });
        });
        return true; // keep the message channel open for async response
      }
      if (result !== undefined) {
        sendResponse(result);
      }
    });
  },

  storage: {
    /**
     * Read one or more keys from local storage.
     * @param {string|string[]} keys
     * @returns {Promise<object>} Object with requested key/value pairs.
     */
    get(keys) {
      return chrome.storage.local.get(keys);
    },

    /**
     * Write key/value pairs to local storage.
     * @param {object} items - e.g. { token: "abc123" }
     * @returns {Promise<void>}
     */
    set(items) {
      return chrome.storage.local.set(items);
    },

    /**
     * Remove one or more keys from local storage.
     * @param {string|string[]} keys
     * @returns {Promise<void>}
     */
    remove(keys) {
      return chrome.storage.local.remove(keys);
    },
  },

  /**
   * Get the extension's internal URL for a resource.
   * @param {string} path - Relative path within the extension.
   * @returns {string} Full URL.
   */
  getURL(path) {
    return chrome.runtime.getURL(path);
  },
};

export default BrowserAPI;
