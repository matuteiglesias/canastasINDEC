# Canastas básicas regionales — INDEC

Serie mensual de Canasta Básica Alimentaria (CBA) y Canasta Básica Total (CBT) organizada por región de Argentina.

> **Estado:** snapshot en mantenimiento. El output versionado llega hasta diciembre de 2025, pero la fuente, las unidades y el pipeline no fueron revalidados en 2026. La presencia de fechas futuras respecto de la última ejecución no demuestra que sean observaciones oficiales.

## Producto principal

```text
data/CB_Reg_defl_m.csv
```

El archivo utiliza un formato largo con las columnas:

| Columna | Contenido |
|---|---|
| `Q` | período mensual |
| `Region` | región estadística |
| `CBA` | valor de la canasta alimentaria |
| `CBT` | valor de la canasta total |

Las regiones incluidas son Cuyo, Gran Buenos Aires, Noreste, Noroeste, Pampeana y Patagonia.

## Uso rápido

```python
import pandas as pd

canastas = pd.read_csv(
    "data/CB_Reg_defl_m.csv",
    parse_dates=["Q"],
)

print(canastas.groupby("Region").tail(1))
```

## Interpretación y procedencia

Este repositorio conserva una **serie procesada derivada de publicaciones del INDEC**. No es una publicación oficial y no debe utilizarse sin verificar:

- la unidad y base monetaria;
- la composición de los hogares de referencia;
- la fecha del último dato observado;
- la metodología de prolongación o deflación;
- cambios en los archivos fuente.

En el tramo final del CSV existen valores repetidos durante varios meses. Esos registros requieren revisión antes de tratarlos como datos observados.

## Autoridad y límites

El repositorio posee el snapshot y su transformación histórica. INDEC conserva la autoridad sobre las canastas publicadas; los análisis posteriores deben citar tanto la fuente oficial como el commit de este repositorio.

## Próxima revisión útil

1. identificar el script o notebook canónico que genera `CB_Reg_defl_m.csv`;
2. recuperar las fuentes y metadatos exactos;
3. declarar observaciones, interpolaciones y proyecciones por separado;
4. agregar una verificación de cobertura y unidades;
5. decidir si la actualización automática debe reactivarse.

Hasta completar esa revisión, usar el archivo como snapshot histórico versionado.

## Posible cambio de nombre

`canastasINDEC` describe el tema, pero `canastas-indec-regionales` explicaría mejor el producto y su alcance geográfico.
