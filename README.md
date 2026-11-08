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

## Cruce con la web oficial

El workflow puede fusionar el snapshot de la API con el catálogo de la web oficial (`python -m shopwatch.official`), pero solo cuando existe `data/official-latest.json` y su fecha de tienda coincide con la del snapshot; si no, el paso se salta y el reporte queda solo con datos de la API. Reglas de la fusión:

- Los tiles que no son PaVos (dinero real) se ignoran y solo se cuentan.
- Duplicados viejos de la API (mismo set de artículos, otro offerId/precio) se quitan únicamente cuando el catálogo oficial confirma cuál es el offerId vigente; sin datos oficiales no se borra nada.
- Si un tile oficial trae la lista de artículos del lote, los faltantes respecto de la API se registran en el reporte lateral (`<salida>.official-report.json`) sin modificar la oferta.
- Nombres: para ofertas presentes en la API manda el nombre de la API (español); los tiles que solo existen en la web oficial entran con el título del tile y `provenance: official-web`.

El scrape oficial necesita navegador en la nube (Cloudflare bloquea el fetch plano), así que hoy esa captura queda fuera de Actions como etapa puente; el merge en CI solo aplica cuando el catálogo oficial del día ya está en `data/`.
