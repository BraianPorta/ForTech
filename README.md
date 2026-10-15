# Circuit Quest

Prototipo de videojuego de retos científicos para Programación científica en Python.
La partida se centra en elegir piezas y activar un dispositivo. Las gráficas se
reservan a las estadísticas del jugador, fuera de la pantalla de juego.

![Pantalla de juego](output/preview.png)

## Ejecutar desde VS Code

Abre la carpeta C:\GitHub\ForTech. El entorno .venv ya está preparado en este equipo.
En la terminal integrada, ejecuta:

```powershell
cd C:\GitHub\ForTech
.\.venv\Scripts\python.exe .\main.py
```

También puedes pulsar F5 y elegir «Circuit Quest · Jugar». La extensión Python de
Microsoft debe estar instalada. En Visual Studio completo, selecciona el intérprete
.venv\Scripts\python.exe y main.py como archivo de inicio.

Para instalarlo en otro equipo con Python 3.12 o posterior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

Se incluye PySide6-Essentials; no hacen falta nuevas dependencias para esta versión.
Las fuentes DejaVu se distribuyen con su licencia en assets/fonts/.

## Cómo se juega

1. Consulta el nivel y su objetivo en la tarjeta de la izquierda.
2. Pulsa el recuadro de R1 o C1. El inventario aparece encima de esa pieza.
3. Elige una de las seis opciones disponibles. No hay campos para escribir valores.
4. Pulsa «ACTIVAR» para probar la configuración.
5. Si falla, cambia otra pieza y vuelve a probar. Si aciertas, aparece la pantalla
   «¡NIVEL SUPERADO!», con tu tiempo, cambios e intentos.
6. Pasa a la siguiente misión o consulta «Mi progreso».

El inventario se cierra al elegir una pieza, pulsar fuera o usar Escape.
Reiniciar comienza una partida nueva del mismo nivel. Tras la última misión,
«Siguiente misión» vuelve a la primera para poder practicar de nuevo.

La interfaz tiene una estética arcade clara: fondo crema, escenario lila,
placa verde, piezas de juguete y un robot que despierta al resolver el circuito.
El objetivo queda a la izquierda y los contadores arriba. Solo se muestra una
indicación para cambiar piezas y una pista breve tras un intento fallido.
El robot flota suavemente y cambia de expresión; las piezas, el inventario,
la victoria y los cambios de nivel mantienen sus animaciones sin bloquear el juego.

## Ejemplo de la primera misión

La fuente es de 5 V, R1 empieza en 1000 Ω y C1 en 470 µF. El objetivo es llegar a
3.3 V a los 0.6 s, con una tolerancia de ±0.15 V.

La configuración inicial da aproximadamente 3.605 V y no cumple el objetivo.
Pulsa C1, elige 560 µF y activa el circuito. Se obtienen aproximadamente 3.287 V:
la misión queda resuelta.

## Estadísticas del jugador

El marcador muestra tiempo transcurrido, sustituciones e intentos de activación.
Solo cuenta como cambio elegir un valor diferente al instalado. Abrir el inventario
o volver a pulsar el mismo valor no aumenta el contador.

El cronómetro empieza al cargar la misión y se congela al resolverla. Consultar el
progreso no pausa una partida activa. Reiniciar descarta la partida no completada
y reinicia tiempo, cambios e intentos. Solo se guardan las misiones resueltas.

El historial se guarda automáticamente en output/progreso.csv y se recupera al
volver a abrir el juego. Incluye identificador de partida, fecha UTC, misión,
dispositivo, tiempo, cambios de R1/C1, cambios totales y número de pruebas.

«Mi progreso» muestra gráficas Matplotlib del tiempo por partida y de las
sustituciones por componente. Si no has completado misiones, presenta un mensaje
vacío, sin inventar datos. Las gráficas muestran las últimas diez partidas;
el CSV conserva el historial completo.

## Datos y modelo científico

Los niveles se leen automáticamente desde data/retos.csv. La gestión de archivos
queda fuera de la interfaz del jugador. Para preparar otro nivel se edita ese
archivo como parte del desarrollo.

Columnas: id, nombre, voltaje_v, resistencia_ohm, capacidad_uf, objetivo_v,
tiempo_objetivo_s, tolerancia_v y descripcion. Se usa UTF-8, coma como separador
y punto decimal. Los valores de los componentes elegibles están en CATALOG,
dentro de game_session.py.

El circuito RC ideal sigue la ecuación:

```text
dVc/dt = (Vs - Vc) / (R*C)
Vc(0) = 0
Vc(t) = Vs * (1 - exp(-t/(R*C)))
Victoria si abs(Vc(t_objetivo) - V_objetivo) <= tolerancia
```

SciPy integra el modelo y NumPy representa las muestras como ndarray. pandas
lee los niveles y escribe el historial. Matplotlib visualiza las métricas del
jugador. Las funciones y estructuras se documentan en los módulos.

Se omiten fugas, tolerancias de fabricación y carga del sensor. El éxito evalúa
la tensión en el instante indicado; no implica regulación de tensión permanente.
El tema y las reglas finales siguen pendientes de acordar para la entrega académica.

## Estructura del código

- main.py: inicio del juego y captura opcional.
- interface.py: partida, inventario, victoria y estadísticas.
- game_widgets.py: escena, componentes, ilustración y cálculo en segundo plano.
- game_style.py: colores y estilos del juego.
- motion.py: fundidos y desplazamientos de interfaz.
- game_session.py: cronómetro, contadores, catálogo y guardado de progreso.
- scientific_model.py: lectura, validación y simulación física.
- data/retos.csv: misiones predefinidas.
- tests/: comprobaciones numéricas y de persistencia.
- tools/verify_interface.py: prueba de una partida completa sin abrir el escritorio.

## Verificación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\verify_interface.py
.\.venv\Scripts\python.exe main.py --preview output/preview.png
```

La prueba de interfaz usa un historial temporal independiente del progreso del
jugador y genera capturas en output/. Comprueba selección de piezas, catálogo
cerrado, intento fallido, victoria, animaciones, reinicio y estadísticas separadas.

## Fuentes

- OpenStax, University Physics Volume 2, 10.5 RC Circuits:
  https://openstax.org/books/university-physics-volume-2/pages/10-5-rc-circuits
- SciPy, solve_ivp:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- NumPy, ndarray:
  https://numpy.org/doc/stable/reference/arrays.ndarray.html
- pandas, read_csv:
  https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
- Matplotlib, integración Qt:
  https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_qt_sgskip.html
- Qt for Python, animaciones:
  https://doc.qt.io/qtforpython-6/overviews/qtcore-animation-overview.html

Este prototipo todavía no incluye la memoria PDF de la entrega final.
