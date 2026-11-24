# -*- coding: utf-8 -*-
"""
Optimización de código y análisis del flujo de datos — programa de ejemplo
Lenguajes y Autómatas II · Equipo 3

Un mini-optimizador que trabaja sobre CÓDIGO DE TRES DIRECCIONES (como el
código intermedio de un compilador o el Jimple de Soot) y aplica, en el mismo
orden que la exposición, las técnicas vistas:

    1. Plegado de constantes          4. Subexpresiones comunes
    2. Propagación de constantes      5. Código invariante en ciclos
    3. Eliminación de código muerto   6. Reducción de intensidad

Las decisiones se toman con ANÁLISIS DEL FLUJO DE DATOS sobre el grafo de
flujo de control (GFC):
    - Definiciones alcanzables  (hacia adelante, unión)        -> pasos 2 y 5
    - Variables vivas           (hacia atrás,   unión)         -> pasos 3 y 5
    - Dominadores               (hacia adelante, intersección) -> paso 5 (ciclos)

Al final un intérprete ejecuta el código ANTES y DESPUÉS con cientos de
entradas aleatorias para comprobar que el resultado es idéntico (criterio:
"preservar el significado") y cuenta cuántas operaciones se ahorraron.

Uso:
    python optimizador_demo.py              # todas las secciones
    python optimizador_demo.py --seccion 2  # solo una sección (1-6)
    python optimizador_demo.py --pausa      # pausa entre secciones (para exponer)
"""

import argparse
import dis
import inspect
import random
import sys
import timeit
from collections import Counter
from itertools import zip_longest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


from optimizador import (ORDEN_CAT, GFC, Programa, alcanzan_por_instr, defs_alcanzables,
                         definida, ejecutar, fmt, listado, optimizar, parsear,
                         propagacion_constantes)


# =============================================================================
# Verificación y conteo (el núcleo del optimizador está en optimizador.py)
# =============================================================================

def verificar(p1, p2, generador, pruebas=500, semilla=2026):
    rnd = random.Random(semilla)
    for _ in range(pruebas):
        args, arr = generador(rnd)
        r1, r2 = ejecutar(p1, args, arr), ejecutar(p2, args, arr)
        if (r1.valor, r1.salida, r1.memoria) != (r2.valor, r2.salida, r2.memoria):
            print(f"  ✗ DIFERENCIA con args={args}: {r1.valor} vs {r2.valor}")
            return False
    if pruebas == 1:
        print(f"  ✓ ANTES y DESPUÉS devuelven el mismo resultado ({r1.valor}).")
    else:
        print(f"  ✓ {pruebas} entradas aleatorias: ANTES y DESPUÉS dan exactamente el mismo resultado.")
    return True


def ops_por_vuelta(prog, crear):
    """Operaciones de UNA vuelta del ciclo = conteo(n=11) − conteo(n=10)."""
    c10 = ejecutar(prog, *crear(10)).contador
    c11 = ejecutar(prog, *crear(11)).contador
    return Counter({k: c11[k] - c10[k] for k in ORDEN_CAT})


# =============================================================================
# 6. Utilidades de impresión
# =============================================================================

def titulo(texto):
    print("\n" + "=" * 78)
    print(f"  {texto}")
    print("=" * 78)


def subtitulo(texto):
    print(f"\n--- {texto} " + "-" * max(0, 72 - len(texto)))


def lado_a_lado(izq, der, t1="ANTES", t2="DESPUÉS", ancho=38):
    print(f"\n  {t1:<{ancho}}{t2}")
    print("  " + "-" * (ancho - 4) + "    " + "-" * (ancho - 4))
    for a, b in zip_longest(izq, der, fillvalue=""):
        print(f"  {a:<{ancho}}{b}")


def tabla_ops(antes, despues, titulo_tabla):
    print(f"\n  {titulo_tabla}")
    print(f"  {'Operación':<26}{'Antes':>8}{'Después':>10}{'Ahorro':>9}")
    print("  " + "-" * 53)
    for cat in ORDEN_CAT:
        a, d = antes[cat], despues[cat]
        if a or d:
            dif = a - d
            print(f"  {cat:<26}{a:>8}{d:>10}{(f'-{dif}' if dif > 0 else ('+' + str(-dif) if dif < 0 else '0')):>9}")


def conj(s, nombres):
    return "{" + ", ".join(sorted((nombres[d] for d in s), key=lambda t: int(t[1:]))) + "}" if s else "∅"


def nombres_defs(codigo):
    return {i: f"d{k}" for k, i in enumerate((i for i, ins in enumerate(codigo) if definida(ins)), 1)}


def pausa(activa):
    if activa:
        input("\n  [Enter para continuar] ")


# =============================================================================
# 7. Secciones de la demostración (siguen el orden de la exposición)
# =============================================================================

EJ1_C = """\
for (i = 0; i < n; i++) {
    y = a * b;
    k = 2 * 3.14;
    v[i] = y + k * i;
}"""

EJ1_TAC = """
    i = 0
L1:
    if i >= n goto L2
    y = a * b
    k = 2 * 3.14
    t1 = k * i
    t2 = y + t1
    v[i] = t2
    i = i + 1
    goto L1
L2:
    return
"""

EJ2_C = """\
int procesa(int v[], int n, int k) {
    int debug = 0;
    int escala = 4 * 8;
    int suma = 0;
    for (int i = 0; i < n; i++) {
        int lim = k * escala;
        if (debug) printf("%d\\n", i);
        int a = v[i] * 2 + lim;
        int b = v[i] * 2 + lim;
        suma = suma + a + b;
    }
    return suma;
}"""

EJ2_TAC = """
    debug = 0
    escala = 4 * 8
    suma = 0
    i = 0
L1:
    if i >= n goto L2
    lim = k * escala
    if debug == 0 goto L3       // if (debug) printf(...)
    print i
L3:
    t1 = v[i]
    t2 = t1 * 2
    a = t2 + lim                // a = v[i] * 2 + lim
    t3 = v[i]
    t4 = t3 * 2
    b = t4 + lim                // b = v[i] * 2 + lim
    t5 = suma + a
    suma = t5 + b
    i = i + 1
    goto L1
L2:
    return suma
"""

CICLO_TAC = """
    i = 0          // d1
    s = 0          // d2
L1:
    s = s + i      // d3
    i = i + 1      // d4
    if i < n goto L1
    return s
"""

ALCANZABLES_TAC = """
    x = 5          // d1
    y = x + 2      // d2
    x = 10         // d3
    z = x + y      // d4
    return z
"""


def seccion_1():
    titulo("EJEMPLO 1 · Antes y después (diapositiva 8)")
    print("\n  Código fuente original (C):\n")
    print("\n".join("    " + l for l in EJ1_C.splitlines()))
    prog = Programa("ejemplo1", parsear(EJ1_TAC))
    print("\n  El compilador lo traduce a código de tres direcciones y lo optimiza:")
    opt = optimizar(prog)
    lado_a_lado(listado(prog.codigo), listado(opt.codigo))

    def crear(n, a=3, b=4):
        return {"n": n, "a": a, "b": b}, {"v": [0] * n}

    tabla_ops(ops_por_vuelta(prog, crear), ops_por_vuelta(opt, crear), "Operaciones en UNA vuelta del ciclo:")
    print("\n  Resultado: mismo comportamiento, 2 multiplicaciones menos por iteración.")
    print("  (k = 6.28 además se propagó dentro del ciclo, por eso k ya ni existe.)")
    print()
    verificar(prog, opt, lambda r: crear(r.randint(0, 15), r.randint(-20, 20), r.randint(-20, 20)))


def seccion_2():
    titulo("EJEMPLO 2 · Un caso más completo, paso a paso (diapositivas 9-11)")
    print("\n  Código fuente original (C):\n")
    print("\n".join("    " + l for l in EJ2_C.splitlines()))
    prog = Programa("procesa", parsear(EJ2_TAC))
    print("\n  Traducido a código de tres direcciones:\n")
    print("\n".join("    " + l for l in listado(prog.codigo)))
    subtitulo("Qué hace el optimizador")
    opt = optimizar(prog)
    lado_a_lado(listado(prog.codigo), listado(opt.codigo))
    print("\n  Equivale en C a:\n")
    print("    int procesa(int v[], int n, int k) {")
    print("        int suma = 0;")
    print("        int lim = k << 5;              // k*32, una sola vez")
    print("        for (int i = 0; i < n; i++) {")
    print("            int a = (v[i] << 1) + lim;")
    print("            suma = suma + a + a;       // b = a")
    print("        }")
    print("        return suma;")
    print("    }")

    def crear(n, k=7, rnd=None):
        rnd = rnd or random.Random(1)
        return {"n": n, "k": k}, {"v": [rnd.randint(-100, 100) for _ in range(n)]}

    tabla_ops(ops_por_vuelta(prog, crear), ops_por_vuelta(opt, crear),
              "OPERACIONES POR VUELTA DEL CICLO:")
    r1 = ejecutar(prog, *crear(1000)).contador["instrucciones totales"]
    r2 = ejecutar(opt, *crear(1000)).contador["instrucciones totales"]
    print(f"\n  Con n = 1000: {r1} instrucciones -> {r2} instrucciones "
          f"({100 * (r1 - r2) / r1:.0f}% menos trabajo).")
    print("\n  ¿Es seguro? Se comprueba ejecutando ambas versiones:")
    verificar(prog, opt, lambda r: crear(r.randint(0, 15), r.randint(-50, 50), r))
    print("  (lim es local y solo se usa dentro del ciclo: sacarlo no cambia nada aunque n = 0.)")


def seccion_3():
    titulo("ANÁLISIS DEL FLUJO DE DATOS · GEN, KILL y punto fijo (diapositivas 13-15)")
    prog = Programa("ciclo", parsear(CICLO_TAC))
    g = GFC(prog.codigo)
    nom = nombres_defs(prog.codigo)
    print("\n  Programa y sus bloques básicos:\n")
    for b, idxs in enumerate(g.bloques):
        for k, i in enumerate(idxs):
            etiqueta = f"B{b + 1}" if k == 0 else ""
            d = f"   ({nom[i]})" if i in nom else ""
            print(f"    {etiqueta:<5}{fmt(prog.codigo[i]):<22}{d}")
    print("\n  Aristas del GFC: " + ", ".join(f"B{b + 1}→B{s + 1}" for b in range(len(g.bloques))
                                             for s in g.suc[b]))

    traza = []
    gen, kill, IN, OUT = defs_alcanzables(g, traza)
    subtitulo("PASO 1 · GEN y KILL de cada bloque")
    print(f"\n    {'Bloque':<8}{'GEN':<16}{'KILL':<16}")
    for b in range(len(g.bloques)):
        print(f"    B{b + 1:<7}{conj(gen[b], nom):<16}{conj(kill[b], nom):<16}")
    print("\n    ¿Por qué KILL[B1] = {d3, d4}? B1 define i y s; cualquier otra definición")
    print("    de i (d4) o de s (d3) queda anulada al pasar por B1.")

    subtitulo("PASO 2 · Aplicar las ecuaciones hasta que nada cambie")
    print("\n    OUT[B] = GEN[B] ∪ (IN[B] − KILL[B])      IN[B] = ∪ OUT[P]      Inicio: OUT = ∅")
    previo = None
    for v, (ins, outs) in enumerate(traza, 1):
        print(f"\n    Vuelta {v}:")
        for b in range(len(g.bloques)):
            marca = ""
            if previo and (ins[b] != previo[0][b] or outs[b] != previo[1][b]):
                marca = "   ← cambió"
            print(f"      B{b + 1}:  IN = {conj(ins[b], nom):<18} OUT = {conj(outs[b], nom):<14}{marca}")
        if previo and all(ins[b] == previo[0][b] and outs[b] == previo[1][b] for b in range(len(g.bloques))):
            print("      Nada cambió → PUNTO FIJO.")
        previo = (ins, outs)

    rd = alcanzan_por_instr(g, IN)
    uso = next(i for i, x in enumerate(prog.codigo) if x.tipo == "op" and x.dst == "s")
    llegan_i = {d for d in rd[uso] if definida(prog.codigo[d]) == "i"}
    print(f"\n    Conclusión: a '{fmt(prog.codigo[uso])}' llegan {conj(llegan_i, nom)} para la variable i,")
    print("    así que i NO es constante en el ciclo y el compilador no puede cambiarla por 0.")
    _, cambios = propagacion_constantes(prog.codigo)
    print(f"    Propagación de constantes sobre este programa: "
          f"{'sin cambios ✓' if not cambios else cambios}")


def seccion_4():
    titulo("EJEMPLO · Definiciones alcanzables (diapositiva 17)")
    prog = Programa("alcanzables", parsear(ALCANZABLES_TAC))
    g = GFC(prog.codigo)
    nom = nombres_defs(prog.codigo)
    _, _, IN, _ = defs_alcanzables(g)
    rd = alcanzan_por_instr(g, IN)
    print()
    for i, ins in enumerate(prog.codigo):
        etiqueta = nom.get(i, "")
        print(f"    {etiqueta + ':' if etiqueta else '':<5}{fmt(ins):<14}  llegan aquí: {conj(rd[i], nom)}")
    d4 = next(i for i, n in nom.items() if n == "d4")
    print(f"\n    1) En d4 llegan {conj(rd[d4], nom)}: d2 (para y) y d3 (para x).")
    print("    2) d3 anula a d1 (d1 está en el KILL de d3).")
    print("    3) Propagando constantes: z = 10 + 7 = 17.")
    subtitulo("El optimizador lo hace solo")
    opt = optimizar(prog)
    lado_a_lado(listado(prog.codigo), listado(opt.codigo))
    print()
    verificar(prog, opt, lambda r: ({}, {}), pruebas=1)


def procesa_original(v, n, k):
    debug = 0
    escala = 4 * 8
    suma = 0
    for i in range(n):
        lim = k * escala
        if debug:
            print("i =", i)
        a = v[i] * 2 + lim
        b = v[i] * 2 + lim
        suma = suma + a + b
    return suma


def procesa_optimizada(v, n, k):
    suma = 0
    lim = k << 5
    for i in range(n):
        a = (v[i] << 1) + lim
        suma = suma + a + a
    return suma


def plegado_en_python():
    return 2 * 3.14


def codigo_muerto_en_python():
    if 0:
        print("esto nunca se ejecuta")
    return 1


def seccion_5():
    titulo("COMPILADORES REALES · El compilador de Python también optimiza")
    print("\n  CPython aplica plegado de constantes y elimina código muerto al compilar")
    print("  a bytecode. Lo vemos con el desensamblador (módulo dis):")
    for f in (plegado_en_python, codigo_muerto_en_python):
        subtitulo(f.__name__)
        print()
        print("\n".join("    " + l for l in inspect.getsource(f).rstrip().splitlines()))
        print("\n    Bytecode generado:")
        for ins in dis.get_instructions(f):
            print(f"      {ins.opname:<20}{ins.argrepr}")
    print("\n  → '2 * 3.14' ya es 6.28 en el bytecode y el 'if 0' desapareció por completo.")
    print("  Pero CPython NO hace subexpresiones comunes, ni saca código invariante de")
    print("  los ciclos: eso lo hacen GCC/LLVM con -O2, o el programador a mano (sección 6).")


def seccion_6():
    titulo("MEDIR · Tiempo real de ejecución (buenas prácticas: medir antes y después)")
    n = 300_000
    rnd = random.Random(5)
    v = [rnd.randint(-1000, 1000) for _ in range(n)]
    k = 13
    assert procesa_original(v, n, k) == procesa_optimizada(v, n, k)
    print(f"\n  procesa() con n = {n:,} elementos (mejor de 5 mediciones):\n")
    t1 = min(timeit.repeat(lambda: procesa_original(v, n, k), number=3, repeat=5)) / 3
    t2 = min(timeit.repeat(lambda: procesa_optimizada(v, n, k), number=3, repeat=5)) / 3
    print(f"    Original   : {t1 * 1000:8.2f} ms")
    print(f"    Optimizada : {t2 * 1000:8.2f} ms")
    print(f"    Aceleración: {t1 / t2:8.2f}x   — y ambas devuelven {procesa_original(v, n, k)}")
    print("\n  Regla 90/10: el ciclo es lo que más se ejecuta, por eso ahí rinde optimizar.")


SECCIONES = [seccion_1, seccion_2, seccion_3, seccion_4, seccion_5, seccion_6]


def main():
    ap = argparse.ArgumentParser(description="Demostración de optimización de código")
    ap.add_argument("--seccion", type=int, choices=range(1, len(SECCIONES) + 1),
                    help="ejecuta solo una sección")
    ap.add_argument("--pausa", action="store_true", help="pausa entre secciones")
    args = ap.parse_args()

    print("\n  LENGUAJES Y AUTÓMATAS II · Optimización de código y flujo de datos")
    print("  Equipo 3 — programa de demostración")
    elegidas = [SECCIONES[args.seccion - 1]] if args.seccion else SECCIONES
    for k, s in enumerate(elegidas):
        s()
        if k < len(elegidas) - 1:
            pausa(args.pausa)
    print()


if __name__ == "__main__":
    main()
