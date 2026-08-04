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
