# Twikoo browser SDK

`frontend/public/vendor/twikoo-2.0.17.min.js` is the unmodified non-CloudBase browser distribution from
[`twikoo@2.0.17`](https://www.npmjs.com/package/twikoo/v/2.0.17), downloaded from
`https://registry.npmjs.org/twikoo/-/twikoo-2.0.17.tgz` on 2026-11-06.
Its MIT license is preserved as `LICENSE`. Simplified Chinese is embedded.

The file is served unchanged from Vite's public directory, not fetched from a third-party CDN at runtime.
It must not be served as a transformed JS module: the iframe uses the SDK's classic UMD global.
Upgrade the file, `TWIKOO_VERSION` in `../index.ts`, and the real-SDK browser acceptance test together.
No backend code is vendored here.
