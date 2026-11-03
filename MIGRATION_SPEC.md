# Migración fortnite-shop-watch a Python único (aprobada por Fran 03/11 00:37, "perfecto así")
Para OpenCode (modelos gratis, ventana coordinada). PR-only. Sin FastAPI ni HTTP: batch CLI.

## Objetivo
Un solo lenguaje/comando: `python -m shopwatch` reemplaza `node --experimental-transform-types src/main.ts`.
Paridad total con el pipeline actual + PDF + stats + cross-check oficial. Cero Node residual.

## Estructura propuesta
```
shopwatch/
  __init__.py
  __main__.py        # entry: argparse -> run()
  client.py          # fetch fortnite-api.com/v2/shop?language=es, 3 intentos, timeout 20s, espera 3s
  models.py          # dataclasses: ShopOffer, Snapshot, Change; currency_status()
  normalize.py       # normalizeEntry + resolveName (bundle.name PRIMERO — fix validado) + resolveImageUrl + collectItemNames + resolveCurrency
  diffing.py         # diffSnapshots (paridad src/diff.ts: solo currency verified entra a added/priceChanged/removed)
  report.py          # buildReport/buildBaselineReport (paridad src/report.ts, mismos textos/formato)
  official.py        # cross-check vs scrape oficial JSON + merge overrides (provenance="official-web")
  pdf.py             # = tools/pdf_digest.py actual + sección "Corrección" + página stats (ref: /tmp/cmp/pdf_digest_fixed.py)
  stats.py           # = shop_stats.py de PR15 (solver scipy MILP, método setcover-min-list-price-v2, YA VALIDADO)
  charts.py          # barras nativas reportlab (reemplaza render_chart.js de PR15; ref layout: draw_stats en pdf_digest_fixed.py)
main shim: python -m shopwatch == flujo de src/main.ts (snapshot -> diff -> reports/*.md + *.json -> data/shop-latest.json)
```

## Mapeo de paridad (origen TS -> destino)
- shopClient.ts requestShop/fetchShopSnapshot -> client.py (mismas constantes: SHOP_URL, UA "fortnite-shop-watch/1.0", MAX_ATTEMPTS=3, RETRY_DELAY_MS=3000, validación status==200 + entries/date/hash, error si 0 ofertas válidas).
- resolveName: CAMBIO INTENCIONAL: bundle.name primero (era el bug de los 21 lotes). Resto de la cadena igual (brItems[0], tracks, instruments/cars/lego, devName, offerId).
- resolveImageUrl/collectItemNames/resolveCurrency/normalizeEntry: copiar lógica tal cual.
- diff.ts diffSnapshots: misma semántica (added si no estaba y verified; priceChanged si cambia finalPrice; removed si verified y ya no está).
- report.ts: mismas líneas ("## Cambios en la tienda — DD/MM/YYYY (vs ...)", "### Nuevos/Salieron/Cambios de precio", offerLine con " — ", sale DD/MM/YYYY, baseline por sección).
- main.ts: mismas env (SNAPSHOT_PATH, REPORTS_DIR), misma escritura reports/<fecha>.md/.json + excludedNonVbucks/excludedUnverified + "existing report kept" cuando no hay cambios.
- types.ts currencyStatus: verified/nonVbucks/unverified igual.

## Workflow
.github/workflows/daily-shop.yml: setup-python 3.12, `pip install reportlab pillow scipy numpy`, `python -m shopwatch`. Mismo paso de PR con gh. Borrar package.json/tsconfig/opencode.json/src/ al final (commit separado dentro del PR para review claro).

## Validación obligatoria antes de merge (CI o local)
1. Fixture: /tmp/cmp/shop-2026-11-03-augmented.json como respuesta simulada -> snapshot generado idéntico en schema; nombres de lote oficiales ("Lote de Rambo" etc., 21 casos).
2. Diff contra /tmp/cmp/shop-2026-11-02.json -> 62 added / 48 removed / 0 priceChanged (paridad con reports/2026-11-03.json).
3. Stats: `python -m shopwatch.stats` sobre /tmp/cmp/shop-2026-11-03-audited.json -> 179.550 / 214 / 346, overlap 0 (paridad totals-audited.json).
4. PDF: render de fixture produce 377/377 imágenes y sección Corrección + página stats (gate visual).
5. El workflow viejo de Node no queda referenciado en ningún lado.

## No hacer
- Sin FastAPI/servidor HTTP. Sin reescribir el algoritmo del solver. Sin cambiar esquema de data/shop-latest.json ni reports/ (historial comparable). Sin tocar email (revocado). Primer 429 -> abortar y reportar.
