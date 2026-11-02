# fortnite-shop-watch

Registra los cambios diarios de la tienda de Fortnite.

- Todos los días a las 21:15 (hora de Argentina) un workflow de GitHub Actions consulta la tienda y guarda las diferencias en `reports/`: qué entró, qué salió y qué cambió de precio, con nombres, precios, fechas de salida e imágenes.
- Fuente de datos: https://fortnite-api.com (API pública gratuita, no oficial de Epic).
- La rotación de la tienda ocurre a las 21:00 (hora de Argentina); la corrida de las 21:15 captura la tienda nueva.

## Correr a mano

```
node --experimental-transform-types src/main.ts
```

Guarda el último estado en `data/shop-latest.json` y el reporte del día en `reports/`.

## Disparar el workflow a mano

Desde la pestaña Actions de GitHub: `daily-shop-watch` → `Run workflow`.
