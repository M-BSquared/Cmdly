"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.api — the backend, as promises.

  get(path) and post(path, body) resolve with the reply's JSON. A reply with
  an error status rejects with an Error whose message is the reply's own
  `error` and whose `.body` is the whole reply: a refused SSH connect says in
  it what it needs (`needs`, `connection`), and the caller asks for exactly
  that. A backend that cannot be reached rejects with "Cmdly's backend is not
  answering", the one reason nothing else can say.
*/
Cmdly.api = (function () {
  const UNREACHABLE = "Cmdly's backend is not answering.";

  function handle(res) {
    return res.json().catch(() => ({})).then((body) => {
      if (res.ok) return body;
      const err = new Error((body && body.error) || `${res.status} ${res.statusText}`);
      err.status = res.status;
      err.body = body || {};
      throw err;
    });
  }

  function get(path) {
    return fetch(path, { cache: "no-store" })
      .catch(() => { throw new Error(UNREACHABLE); })
      .then(handle);
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).catch(() => { throw new Error(UNREACHABLE); }).then(handle);
  }

  /** A rejected request as a reply body, for the routes whose 400 says what to ask for. */
  function replyOf(error) {
    return Object.assign({ ok: false, error: (error && error.message) || UNREACHABLE },
      (error && error.body) || {});
  }

  return { get, post, replyOf, UNREACHABLE };
})();
