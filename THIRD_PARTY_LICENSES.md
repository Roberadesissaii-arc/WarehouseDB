# Third-party licenses

This project bundles the following open-source JavaScript libraries in `app/static/js/vendor/`
and `scan/static/js/vendor/`. Store UI SVG icons under `store/static/icons/` were copied from
design packs during development and are committed as project assets.

## Lucide Icons

- **Files:** selected SVGs under `store/static/icons/ui/` (e.g. `orders.svg`, `user.svg`, `help.svg`, `sign-out.svg`) and matching inline SVG in store templates
- **License:** ISC License
- **Source:** https://lucide.dev/icons/

## QRCode.js (davidshimjs/qrcodejs)

- **Files:** `app/static/js/vendor/qrcode.min.js`, `scan/static/js/vendor/qrcode.min.js`
- **License:** MIT
- **Source:** https://github.com/davidshimjs/qrcodejs

## html5-qrcode

- **Files:** `scan/static/js/vendor/html5-qrcode.min.js`
- **License:** Apache License 2.0
- **Source:** https://github.com/mebjas/html5-qrcode

## Python dependencies

Runtime Python packages are listed in `requirements.txt`, `store/requirements.txt`, and
`scan/requirements.txt`. See each package on PyPI for its license terms (Flask, Werkzeug,
waitress, requests).
