(function () {
  'use strict';
  window.addEventListener('message', function (event) {
    var message = event.data || {};
    if (message.type !== 'env.host.context' || !message.payload) return;
    document.documentElement.dataset.theme = message.payload.theme || 'light';
    document.getElementById('context').textContent = '由 Env WebUI 托管 · SDK ' + message.payload.sdkVersion;
  });
  window.parent.postMessage({ type: 'env.host.ready', version: 1 }, '*');
}());
