# Circuit Quest

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
inicia Circuit Quest.

## Organización del código

- `data.py` lee los retos desde `data/retos.csv` y guarda el progreso y las
  exportaciones del juego.
- `ui/shared/functions.py` contiene el modelo y los cálculos científicos que usan
  los ejercicios.
- El panel del circuito llama a `simulate` con las resistencias elegidas por el
  jugador. Calcula la resistencia equivalente: suma las resistencias en serie
  de cada fila y combina hasta tres filas en paralelo.

## Añadir retos

Cada reto se guarda en un archivo `.csv` independiente dentro de `data/`.
El juego carga todos los CSV de esa carpeta y cada archivo debe contener
exactamente una fila de reto. Las columnas obligatorias son
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

Cada `fila_X` es una rama en paralelo; sus resistencias se conectan en serie.
Admite hasta `fila_3`. Por ahora, el tipo admitido es `ohm` (también `resistencia`)
y cada valor correcto debe estar en el catálogo: 330, 680, 1000, 1500, 2200 o
3300 Ω. `resultado` debe coincidir con el equivalente calculado. El juego empieza
con valores candidatos incorrectos; al elegir un componente se puede seleccionar
su valor correcto en el catálogo. `modo=0` muestra el reto a Leire y `modo=1` a
Unai. Un tipo final sin valor se ignora.

## Personajes y menú

En la pantalla inicial, elige un personaje. Leire juega los retos de circuitos
eléctricos; Unai aparece como próximamente hasta que haya retos con `modo=1` en
el CSV.

Durante la partida, pulsa el botón de tres barras para abrir el menú. La partida
queda pausada y puedes reanudarla, volver a la pantalla inicial o consultar el
progreso. Si vuelves a elegir a Leire, continúas la misma partida.
