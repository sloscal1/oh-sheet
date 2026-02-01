/**
 * Promise-queue based rate limiter.
 *
 * Enforces a minimum interval between successive calls so that upstream
 * APIs are never hit faster than the allowed rate.
 *
 * Ported from backend/echomtg_sync/api_client.py _rate_limit().
 */

export default class RateLimiter {
  /**
   * @param {number} requestsPerSecond - Maximum allowed rate (default 2).
   */
  constructor(requestsPerSecond = 2) {
    this._minInterval = 1000 / requestsPerSecond; // ms
    this._lastTime = 0;
    this._queue = Promise.resolve();
  }

  /**
   * Wait until the next request is allowed, then execute `fn`.
   * Calls are serialised: if multiple callers invoke `schedule` concurrently,
   * they queue up and each waits its turn.
   *
   * @template T
   * @param {() => Promise<T>} fn - Async function to execute after the delay.
   * @returns {Promise<T>}
   */
  schedule(fn) {
    this._queue = this._queue.then(() => this._wait()).then(fn);
    return this._queue;
  }

  /** @private */
  async _wait() {
    const now = performance.now();
    const elapsed = now - this._lastTime;
    if (elapsed < this._minInterval) {
      await new Promise((r) => setTimeout(r, this._minInterval - elapsed));
    }
    this._lastTime = performance.now();
  }
}
