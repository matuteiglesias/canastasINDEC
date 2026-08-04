# Canastas regionales — artefacto analítico derivado

Este repositorio conserva una transformación histórica de las series regionales de Canasta Básica Alimentaria (CBA) y Canasta Básica Total (CBT). **`data/CB_Reg_defl_m.csv` no es una serie oficial observada de canastas mensuales.**

> **Estado:** mantenimiento correctivo. El artefacto comprometido llega hasta diciembre de 2025, pero los valores observados identificables llegan hasta julio de 2025. Desde agosto de 2025 la cola repite valores por región. La fuente y el pipeline no fueron reejecutados en esta revisión.

## Qué representa realmente el archivo principal

`computar_canastas.py`:

1. descarga series nominales regionales;
2. las deflacta con el índice de `IPC-Argentina` a una referencia de enero de 2016;
3. reindexa el resultado sobre el calendario del IPC desde 2003;
4. completa faltantes con medias de columna;
5. vuelve a expresar **toda la historia** al nivel de precios del mes de ejecución;
6. escribe el resultado en `data/CB_Reg_defl_m.csv`.

Por lo tanto, el archivo mezcla:

- datos derivados de publicaciones oficiales;
- períodos anteriores al inicio declarado de la fuente regional;
- imputación por medias;
- la fecha y proyecciones disponibles en `IPC-Argentina`;
- una expresión monetaria dependiente del mes en que se ejecutó el script.

No debe utilizarse para citar niveles oficiales corrientes de CBA o CBT.

## Estado verificable

La declaración auditable vive en [`DATA_STATUS.json`](DATA_STATUS.json). Para comprobar que el snapshot comprometido conserva las fronteras declaradas:

```bash
python scripts/verify_snapshot.py
```

El chequeo es local y sin red. Valida:

- esquema y cobertura del CSV;
- seis regiones por período;
- fecha máxima;
- cola sintética repetida desde agosto de 2025.

No valida la fuente oficial ni la corrección metodológica de la transformación.

## Linaje y contrato de lanzamiento

La [clasificación de familias](docs/BASKET_PRODUCT_FAMILIES.md), el
[grafo de transformaciones](contracts/lineage_graph.json) y los diccionarios en
`contracts/` documentan el snapshot sin cambiar sus valores. La clasificación
por celda del artefacto principal se reproduce localmente con:

```bash
make basket-lineage-report
```

Una entrega **completamente sintética** demuestra el sobre de manifiesto y el
preflight de compatibilidad, sin representar umbrales reales:

```bash
make release-fixture
make release-check
```

La [evaluación del slice](docs/POVERTY_SLICE_BASKET_READINESS.md) explica por
qué todavía no puede emitirse un candidato real reproducible. Ninguno de estos
comandos consulta la red ni sobrescribe los CSV reales comprometidos.

## Constructor de candidatos observado-nominales

La adquisición queda separada de la construcción. `basket-source-lock` es la
única etapa que contacta las distribuciones oficiales 445.1 y 446.1; el
candidato se reconstruye sin red desde ese lock y una **copia inmutable** de un
release candidato de precios. Nunca consulta una rama de `IPC-Argentina` ni
ejecuta un checkout hermano:

```bash
make basket-source-probe
make basket-source-lock
make basket-source-lock-check SOURCE_LOCK=run/source_lock.json
make basket-candidate SOURCE_LOCK=run/source_lock.json PRICE_RELEASE=/copias/ipc-release-id
make basket-candidate-check RELEASE_DIR=artifacts/basket_releases/release-id
make poverty-basket-2024q1 RELEASE_DIR=artifacts/basket_releases/release-id
```

El núcleo incluye solamente meses completos observados en fuente, sin backcast,
relleno ni cola repetida. La conversión a referencia enero de 2016 y las medias
trimestrales son derivados separados. El bundle 2024-Q1 es sólo un insumo de
investigación de seis regiones: no calcula pobreza ni inventa un mapa provincial.

## Uso recomendado

Para análisis nuevos, preferir las series oficiales nominales como entrada y construir un producto nuevo con:

- procedencia y fecha de descarga;
- períodos observados separados de imputaciones y proyecciones;
- unidad monetaria explícita;
- una política de deflación versionada;
- un manifest de ejecución.

Este repositorio puede seguir siendo útil como evidencia histórica del método, pero no debe propagarse como una capa de datos actuales sin esa reparación.

## Dependencia

El pipeline consume:

```text
IPC-Argentina/data/info/indice_precios_M.csv
```

Si esa serie contiene meses proyectados, esos meses pueden propagarse a este output. La frescura de este repositorio nunca puede ser mayor que la de esa dependencia.
