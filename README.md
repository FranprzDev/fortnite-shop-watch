# fortnite-shop-watch

Registra los cambios diarios de la tienda de Fortnite.

- Todos los días a las 21:15 (hora de Argentina) un workflow de GitHub Actions consulta la tienda y abre un PR diario con las diferencias: qué entró, qué salió y qué cambió de precio, con nombres, precios, fechas de salida e imágenes. Nunca escribe directo en `main`: los cambios quedan en un PR para revisar y mergear.
- Fuente de datos: https://fortnite-api.com (API pública gratuita, no oficial de Epic).
- La rotación de la tienda ocurre a las 21:00 (hora de Argentina); la corrida de las 21:15 captura la tienda nueva.

## Correr a mano

Requiere Python 3.12 e instalar las dependencias:

```
pip install reportlab pillow scipy numpy
```

```
python -m shopwatch
```

Guarda el último estado en `data/shop-latest.json` y el reporte del día en `reports/`.

## Disparar el workflow a mano

Desde la pestaña Actions de GitHub: `daily-shop-watch` → `Run workflow`.

Requiere Python 3.12 (el CI corre 3.12). Las dependencias usan rangos con piso y techo (no lockfile): pip resuelve la versión más nueva dentro del rango en cada instalación, y `pip-audit` corre en CI sobre la resolución real.

## Cruce con la web oficial

El workflow puede fusionar el snapshot de la API con el catálogo de la web oficial (`python -m shopwatch.official`), pero solo cuando existe `data/official-latest.json` y su fecha de tienda coincide con la del snapshot; si no, el paso se salta y el reporte queda solo con datos de la API. Reglas de la fusión:

- Los tiles que no son PaVos (dinero real) se ignoran y solo se cuentan.
- Duplicados viejos de la API (mismo set de artículos, otro offerId/precio) se quitan únicamente cuando el catálogo oficial confirma cuál es el offerId vigente; sin datos oficiales no se borra nada.
- Si un tile oficial trae la lista de artículos del lote, los faltantes respecto de la API se registran en el reporte lateral (`<salida>.official-report.json`) sin modificar la oferta.
- Nombres: para ofertas presentes en la API manda el nombre de la API (español); los tiles que solo existen en la web oficial entran con el título del tile y `provenance: official-web`.

El scrape oficial necesita navegador en la nube (Cloudflare bloquea el acceso desde IPs de datacenter, verificado con Chromium headless en un runner de Actions), así que la captura queda fuera de Actions como etapa puente asistida: la captura diaria llega en el PR del día como `data/official-latest.json`.

La reconciliación se valida en dos puntos, ambos con la misma lógica de fecha testeada (`--check-date`):

- **Job programado** (`daily-shop.yml`): fusiona el snapshot con el catálogo oficial solo si ambos llevan la misma fecha de tienda; si no, se salta.
- **Gate de PR** (`test.yml`, job `official-reconcile`): cuando el PR del día incluye `data/official-latest.json` con la fecha del snapshot, corre el merge en modo verificación y falla si hay `price_mismatches` (`--fail-on-price-mismatch`); el reporte lateral queda como artifact del run. Si el PR no trae captura de la misma fecha (PR solo-API o de código), el gate se salta sin fallar.
