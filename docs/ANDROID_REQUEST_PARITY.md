# Android request parity contract

This document records the exact request-shape evidence recovered from the installed official myQ Android app (`5.243.1.73243`). It exists so the Pi-native client can be kept intentionally boring and app-shaped instead of accumulating tolerated-but-unproven headers or retries.

## Command request

The current APK's v6 GDO Retrofit interface declares `open` and `close` as bodyless `PUT` requests:

```text
PUT api/{apiVersion}/accounts/{accountId}/door_openers/{serialNumber}/open
PUT api/{apiVersion}/accounts/{accountId}/door_openers/{serialNumber}/close
```

The concrete v6 service supplies the API-version path value, account ID, and serial number only. There is no Retrofit request-body parameter for either operation. The Pi client must therefore send exactly one bodyless PUT for an authorized mutation and must never retry or fail over after that mutation is attempted.

## Android network interceptor

The official network interceptor handles authentication separately from public app metadata.

For normal authenticated API calls it adds the current bearer token when the request does not already contain `Authorization` and the request is not classified as an OAuth request.

From the framework configuration map it explicitly whitelists only these four headers for propagation:

```text
MyQApplicationId
User-Agent
BrandId
App-Version
```

Do not add unrelated convenience headers merely because the backend currently tolerates them. In particular, `Culture` and `ApiVersion` were found elsewhere in the APK/configuration model, but they are not members of this interceptor's four-header propagation whitelist. The v6 API version for GDO actions is a path parameter, not evidence for an `ApiVersion` request header.

## OAuth requests

The same interceptor explicitly recognizes OAuth requests and does **not** add the bearer `Authorization` header to them. It sets the form content type for the OAuth request path:

```text
Content-Type: application/x-www-form-urlencoded
```

The four whitelisted public app headers above still pass through when configured. Token refresh/exchange code should therefore not reuse the authenticated API header dictionary wholesale.

## Required Pi-client separation

Maintain separate request builders:

- authenticated API headers: bearer token + the four whitelisted public app headers;
- OAuth headers: form content type + the four whitelisted public app headers, without bearer authorization;
- mutation body: empty for GDO open/close;
- no mutation replay after any ambiguous response;
- read-only retries are allowed only for the narrowly defined token-refresh path already covered by tests.

Before promoting a future APK protocol profile, re-audit the Retrofit GDO methods and this interceptor whitelist. A change in either is protocol drift even if the endpoint still returns successful read responses.

## 2026-09-10 validation note

The Pi-native status path is deployed and returns the configured garage state correctly. Broadlink keeps state cache-only by default and performs a live MyQ read only on explicit recheck or a safety-critical action preflight.

A production-path `open` test while the garage reported `closed` resulted in a single accepted request but no sensor transition. This is not evidence that the endpoint shape is wrong: the owner subsequently clarified that the physical opener will not actuate unless `Levi's Plug` is powered. Do not repeat mutation requests merely to investigate that condition. Status/read validation is sufficient while request parity is being tightened.
