# ForTech

## Requisitos

- Python 3.12 o posterior.
- `pip`, incluido normalmente con Python.

## Instalación y ejecución

Abre una terminal en la carpeta del proyecto y ejecuta:

```powershell
python -m pip install -r requirements.txt
python main.py
```

El primer comando instala las dependencias del juego. Cuando termine, el segundo
inicia ForTech.

## Organización del código

- `data/import/` contiene temporalmente un archivo CSV por reto. Al iniciar,
  `data.py` valida cada archivo, lo agrega a `data/exercises/exercises.csv` con
  un `id` numérico secuencial y elimina el archivo de importación tras guardarlo.
  Ese único CSV es el que carga el juego.
- `data/results/` guarda el progreso (`progreso.csv`), las exportaciones y las
  estadísticas de juego.
- Al completar todas las actividades de una sesión, el juego guarda una fila
  por actividad en `data/results/session/<número>.csv`, con las columnas
  `Tiempo,Cambios,Intentos`. Al consultar las estadísticas desde la pantalla
  inicial, calcula en memoria el resumen y el estilo de cada sesión completada;
  no genera un CSV comparativo.
- `ui/shared/functions/electronic.py` contiene el modelo y los cálculos eléctricos.
- `ui/shared/functions/flow.py` contiene los datos, ecuaciones y cálculos de los ejercicios
  de mecánica de fluidos de Unai.
- El panel del circuito llama a `simulate` con los componentes elegidos por el
  jugador. Calcula la resistencia equivalente, convirtiendo la potencia de las
  bombillas a resistencia con `R = V²/P` cuando corresponde.

## Añadir retos

Cada reto se guarda en un archivo `.csv` independiente dentro de `data/import/`
y debe contener exactamente una fila. Al iniciar el juego se importa, se añade
al único archivo `data/exercises/exercises.csv` con el siguiente `id` numérico
disponible y se elimina el archivo de entrada. Las columnas obligatorias son
`modo,dificultad,enunciado,resultado`; `dificultad` debe ser un número entre
1 y 3. Añade pares de columnas `tipo_1,valor_1`,
`tipo_2,valor_2`, etc. para describir el circuito en orden. El lector detecta
automáticamente cuántos pares hay en la cabecera, así que cada fila puede
terminar en su último dato sin rellenar con separadores las columnas restantes.
Usa un marcador `fila_1` en una columna `tipo_X` y deja vacío su `valor_X`,
seguido de los pares tipo/valor de los componentes. Por ejemplo:

```csv
modo,dificultad,enunciado,resultado,tipo_1,valor_1,tipo_2,valor_2,tipo_3,valor_3,tipo_4,valor_4
0,3,Calcula la resistencia equivalente.,500,fila_1,,ohm,1000,fila_2,,ohm,1000
```

Cada `fila_X` es una rama en paralelo; sus componentes se conectan en serie.
Admite hasta `fila_3`. Los tipos `ohm` y `resistencia` usan el catálogo
330, 680, 1000, 1500, 2200 y 3300 Ω. Los tipos `bombilla_w`, `bombilla` y
`bulb_w` usan el catálogo de 3, 6 y 12 W
y requieren la columna opcional `tension_v`; el juego convierte potencia a
resistencia con `R = V²/P`. El tipo `bombilla_ohm` usa el catálogo de 12, 24 y
48 Ω como resistencias de bombillas. Para evaluar la potencia del circuito, se
suman primero las resistencias en serie y se aplica `P = V²/R`.
Opcionalmente, `unidad_resultado` puede ser `W` y `resultado_min`/
`resultado_max` definen un intervalo de éxito inclusivo; `resultado` indica el
valor objetivo de referencia dentro de ese intervalo.
Cuando se indica `tension_v`, el esquema del circuito también muestra la pila
con ese voltaje.
Para Leire, `resultado` debe coincidir con la resistencia equivalente calculada.
Sus retos usan `modo=0`. Los ejercicios de Unai usan `modo=1`, dejan vacíos los
pares `tipo_X`/`valor_X` (o pueden omitir esas columnas) y especifican
`tipo_ejercicio` como `laminar_flow`, `heat_transfer` o `pressure_loss`. Los
parámetros seleccionables, sus opciones, las constantes y las fórmulas se definen en
`ui/shared/functions/flow.py`; el panel muestra el esquema y el contexto del ejercicio y
permite cambiar los parámetros desde una fila de bloques. Un tipo final sin
valor se ignora. En esos ejercicios, `resultado` conserva un valor numérico de
referencia; el criterio de éxito (régimen laminar o intervalo de transferencia/
pérdida) lo define el tipo de ejercicio.

## Personajes y menú

En la pantalla inicial, elige un personaje. Leire juega los retos de circuitos
eléctricos y Unai los ejercicios de mecánica de fluidos identificados con
`modo=1` en el CSV.

Durante la partida, pulsa el botón de tres barras para abrir el menú. La partida
queda pausada y puedes reanudarla o volver a la pantalla inicial. Desde la
pantalla inicial puedes consultar las estadísticas almacenadas; una sesión solo
se incluye en la comparación cuando se han completado todas sus actividades.
Una sesión incompleta no reemplaza ni altera las estadísticas anteriores.
