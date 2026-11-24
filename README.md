# Optimizador de código — Lenguajes y Autómatas II (Equipo 3)

Programa de ejemplo basado en la exposición *Optimización de código: criterios de
mejora y herramientas para el análisis del flujo de datos*.

## Cómo usarlo

- **Interfaz gráfica:** doble clic en `abrir_interfaz.bat`, o `python interfaz.py`
- **Demo de consola (sin interfaz):** `python optimizador_demo.py`, con `--seccion N` (1-6) y `--pausa` como opciones

Solo necesita Python 3.10 o más nuevo. Tkinter viene incluido con Python en Windows.

## Qué hace la interfaz

1. **Abrir archivo** o elegir uno de `ejemplos/`. Los archivos están escritos en C o en
   código de tres direcciones y están **sin optimizar** a propósito.
2. El archivo se traduce a **código intermedio** (panel ②). Las líneas en rojo son las
   que el optimizador cambia o elimina.
3. El panel ③ muestra el **código optimizado**. En verde, lo nuevo o cambiado.
4. Los indicadores de arriba resumen la mejora: instrucciones en el código, instrucciones
   ejecutadas, transformaciones aplicadas y si el resultado sigue siendo el mismo.
5. Pestañas de abajo:
   - **Paso a paso:** qué cambió cada técnica, en orden, hasta el punto fijo.
   - **Ejecutar y comparar:** ejecuta ambas versiones con los datos de entrada, cuenta las
     operaciones por tipo y las grafica. También verifica con 300 entradas aleatorias.
   - **Análisis del flujo de datos:** bloques básicos, GFC, GEN/KILL/IN/OUT de definiciones
     alcanzables, variables vivas, dominadores, ciclos y variables sin inicializar.
6. Las casillas de **Técnicas activas** prenden o apagan cada optimización, para ver
   cuánto aporta cada una.
7. El texto del panel ① se puede editar. Después de editarlo, presiona **F5** para optimizar de nuevo.

Los datos de entrada se toman de la línea `// @entrada: n=1000, k=7, v=aleatorio(1000)`
del archivo. Para arreglos se puede escribir `aleatorio(N)`, `ceros(N)` o `1, 2, 3`.

## Ejemplos incluidos (`ejemplos/`)

| Archivo | Técnica que muestra |
|---|---|
| 01_plegado_constantes.c | Plegado de constantes e identidades algebraicas |
| 02_propagacion_constantes.c | Propagación de constantes |
| 03_codigo_muerto.c | Código inalcanzable y variables que no influyen en el resultado |
| 04_subexpresiones_comunes.c | Subexpresiones comunes |
| 05_codigo_invariante.c | Código invariante en ciclos |
| 06_reduccion_intensidad.c | Reducción de intensidad (`x*8` → `x<<3`) |
| 07_procesa_exposicion.c | Ejemplo 2 de la exposición (las seis técnicas) |
| 08_ejemplo_diapositiva8.c | Ejemplo 1 de la exposición |
| 09_definiciones_alcanzables.c | Ejemplo de definiciones alcanzables (z = 17) |
| 10_matriz_ciclos_anidados.c | Código invariante en ciclos anidados |
| 11_reporte_ventas.c | Programa "realista" con todo junto |
| 12_codigo_intermedio.tac | Entrada escrita directamente en tres direcciones |

## Archivos

- `interfaz.py`: interfaz gráfica (Tkinter)
- `minic.py`: mini-compilador de un subconjunto de C a código de tres direcciones
- `optimizador.py`: GFC, análisis del flujo de datos, las 6 optimizaciones y el intérprete
- `optimizador_demo.py`: demostración por consola que sigue el orden de las diapositivas

## C que se acepta

Una función (o sentencias sueltas), `int`/`float`/`double`, arreglos, `= += -= *= /= %= <<= >>= ++ --`,
`+ - * / % << >>`, comparaciones con `&& || !`, `if/else`, `while`, `do-while`, `for`,
`break`, `continue`, `return` y `printf`. No acepta llamadas a otras funciones, punteros ni conversiones de tipo (*casts*).
