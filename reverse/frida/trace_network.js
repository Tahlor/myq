'use strict';

function scrub(value) {
  if (value === null || value === undefined) return '';
  let s = String(value);
  s = s.replace(/([?&](?:access_token|refresh_token|id_token|token|code|code_verifier|password|secret)=)[^&#]*/gi, '$1<REDACTED>');
  s = s.replace(/(Bearer\s+)[A-Za-z0-9._~+\/-]+=*/gi, '$1<REDACTED>');
  return s;
}

function emit(kind, value) {
  console.log(JSON.stringify({ kind: kind, value: scrub(value), ts: Date.now() }));
}

Java.perform(function () {
  try {
    const URL = Java.use('java.net.URL');
    const init = URL.$init.overload('java.lang.String');
    init.implementation = function (value) {
      emit('url', value);
      return init.call(this, value);
    };
  } catch (e) { emit('hook_error', 'java.net.URL: ' + e); }

  try {
    const ISA = Java.use('java.net.InetSocketAddress');
    const initHost = ISA.$init.overload('java.lang.String', 'int');
    initHost.implementation = function (host, port) {
      emit('socket', host + ':' + port);
      return initHost.call(this, host, port);
    };
  } catch (e) { emit('hook_error', 'InetSocketAddress: ' + e); }

  try {
    const WebView = Java.use('android.webkit.WebView');
    const loadUrl = WebView.loadUrl.overload('java.lang.String');
    loadUrl.implementation = function (url) {
      emit('webview', url);
      return loadUrl.call(this, url);
    };
  } catch (e) { emit('hook_error', 'WebView.loadUrl: ' + e); }

  try {
    const Builder = Java.use('okhttp3.Request$Builder');
    const urlString = Builder.url.overload('java.lang.String');
    urlString.implementation = function (url) {
      emit('okhttp_url', url);
      return urlString.call(this, url);
    };
    const header = Builder.header.overload('java.lang.String', 'java.lang.String');
    header.implementation = function (name, value) {
      const lower = String(name).toLowerCase();
      const safe = /authorization|cookie|token|secret|password|integrity|app.?check/i.test(lower)
        ? '<REDACTED>' : scrub(value);
      emit('okhttp_header', name + ': ' + safe);
      return header.call(this, name, value);
    };
  } catch (e) { emit('hook_error', 'OkHttp Request.Builder: ' + e); }
});
