# -*- coding: utf-8 -*-
"""
Optimizador de código — interfaz gráfica
Lenguajes y Autómatas II · Equipo 3

Abre un archivo SIN optimizar (C o código de tres direcciones), lo traduce a
código intermedio, aplica las optimizaciones y muestra las mejoras:
    - código antes / después con las líneas que cambiaron resaltadas
    - el recorrido paso a paso de cada técnica
    - ejecución de ambas versiones con conteo de operaciones y gráfica
    - verificación con entradas aleatorias (mismo resultado)
    - el análisis del flujo de datos usado para decidir

Ejecutar:  python interfaz.py
"""

import difflib
import glob
import os
import queue
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from minic import ErrorC, compilar_c
from optimizador import (ORDEN_CAT, PASOS, ErrorEjecucion, GFC, ciclos_naturales,
                         contar_instrucciones, defs_alcanzables, definida, dominadores,
                         ejecutar, fmt, leer_entrada, listado, optimizar_registro,
                         posibles_sin_inicializar, programa_desde_tac, use_def_bloques,
                         valor_entrada, verificar_aleatorio, vivas_por_instr)

CARPETA = os.path.dirname(os.path.abspath(__file__))
CARPETA_EJEMPLOS = os.path.join(CARPETA, "ejemplos")

# ---- Paleta -----------------------------------------------------------------
FONDO = "#f9f9f7"
SUPERFICIE = "#fcfcfb"
GUTTER = "#f1f0ec"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TENUE = "#898781"
REJILLA = "#e1e0d9"
EJE = "#c3c2b7"
BORDE = "#dcdbd4"
CABECERA = "#1d2433"
SERIE_ANTES = "#2a78d6"     # sin optimizar (azul)
SERIE_DESPUES = "#eb6834"   # optimizado (naranja)
MEJORA = "#006300"
EMPEORA = "#b42318"
FONDO_QUITADO = "#fbe4e2"
FONDO_NUEVO = "#dff3e4"
FONDO_SELECCION = "#cfe0f7"
COLOR_PASO = ["#2a78d6", "#eb6834", "#1baf7a", "#c98500", "#d55181", "#008300"]

FUENTE_COD = ("Consolas", 11)
FUENTE_UI = ("Segoe UI", 10)

PALABRAS_C = r"\b(int|float|double|long|short|char|void|unsigned|const|if|else|for|while|do|return|break|continue|printf)\b"
PALABRAS_TAC = r"\b(if|goto|return|print)\b"


def miles(n):
    return f"{n:,}".replace(",", " ")


# =============================================================================
# Widgets
# =============================================================================

class PanelCodigo(ttk.Frame):
    """Texto con números de línea, barras de desplazamiento y resaltado."""

    def __init__(self, master, titulo, editable=False, numeros=True):
        super().__init__(master, style="Panel.TFrame")
        cab = ttk.Frame(self, style="Panel.TFrame")
        cab.pack(fill="x", pady=(0, 4))
        ttk.Label(cab, text=titulo, style="PanelTitulo.TLabel").pack(side="left")
        self.info = ttk.Label(cab, text="", style="PanelInfo.TLabel")
        self.info.pack(side="right")

        cuerpo = tk.Frame(self, bg=BORDE, padx=1, pady=1)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.rowconfigure(0, weight=1)
        cuerpo.columnconfigure(1, weight=1)
        self.editable = editable
        self.nums = tk.Text(cuerpo, width=4, height=8, padx=6, pady=6, bd=0, highlightthickness=0,
                            bg=GUTTER, fg=TENUE, font=FUENTE_COD, takefocus=0,
                            cursor="arrow", state="disabled")
        if numeros:
            self.nums.grid(row=0, column=0, sticky="ns")
        self.texto = tk.Text(cuerpo, wrap="none", undo=editable, bd=0, highlightthickness=0, height=8,
                             font=FUENTE_COD, bg=SUPERFICIE, fg=TINTA, insertbackground=TINTA,
                             padx=8, pady=6, selectbackground=FONDO_SELECCION,
                             selectforeground=TINTA, spacing1=1, spacing3=1)
        self.nums.configure(spacing1=1, spacing3=1)
        self.texto.grid(row=0, column=1, sticky="nsew")
        sy = ttk.Scrollbar(cuerpo, orient="vertical", command=self.texto.yview)
        sy.grid(row=0, column=2, sticky="ns")
        sx = ttk.Scrollbar(cuerpo, orient="horizontal", command=self.texto.xview)
        sx.grid(row=1, column=1, sticky="ew")

        def al_desplazar(a, b):
            sy.set(a, b)
            self.nums.yview_moveto(a)
        self.texto.configure(yscrollcommand=al_desplazar, xscrollcommand=sx.set)
        self.nums.bind("<MouseWheel>", lambda e: (self.texto.yview_scroll(-e.delta // 120, "units"), "break")[1])

        self.texto.tag_configure("quitada", background=FONDO_QUITADO)
        self.texto.tag_configure("nueva", background=FONDO_NUEVO)
        self.texto.tag_configure("error", background=FONDO_QUITADO, underline=True)
        self.texto.tag_configure("clave", foreground="#6250d6")
        self.texto.tag_configure("etiqueta", foreground="#0d5c9e", font=FUENTE_COD + ("bold",))
        self.texto.tag_configure("comentario", foreground=TENUE)
        self.texto.tag_configure("numero", foreground="#a3480f")
        self.texto.tag_raise("sel")
        self.texto.bind("<<Modified>>", self._modificado)
        if not editable:
            self.texto.configure(state="disabled")

    def _modificado(self, _=None):
        if self.texto.edit_modified():
            self.actualizar_numeros()
            self.texto.edit_modified(False)

    def actualizar_numeros(self):
        n = int(self.texto.index("end-1c").split(".")[0])
        self.nums.configure(state="normal", width=max(3, len(str(n))))
        self.nums.delete("1.0", "end")
        self.nums.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self.nums.configure(state="disabled")
        self.nums.yview_moveto(self.texto.yview()[0])

    def poner(self, contenido):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", contenido)
        if self.editable:
            self.texto.edit_reset()
        else:
            self.texto.configure(state="disabled")
        self.actualizar_numeros()

    def obtener(self):
        return self.texto.get("1.0", "end-1c")

    def resaltar(self, lineas, tag):
        for n in lineas:
            self.texto.tag_add(tag, f"{n}.0", f"{n}.0 lineend+1c")

    def limpiar_resaltado(self, *tags):
        for t in tags:
            self.texto.tag_remove(t, "1.0", "end")

    def colorear(self, lenguaje):
        t = self.texto
        for tag in ("clave", "etiqueta", "comentario", "numero"):
            t.tag_remove(tag, "1.0", "end")
        contenido = t.get("1.0", "end-1c")

        def marcar(patron, tag, flags=0):
            for m in re.finditer(patron, contenido, flags):
                t.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        marcar(r"(?<![\w.])\d+(\.\d+)?", "numero")
        marcar(PALABRAS_C if lenguaje == "c" else PALABRAS_TAC, "clave")
        if lenguaje != "c":
            marcar(r"^\s*\w+:", "etiqueta", re.M)
            marcar(r"\bgoto\s+(\w+)", "etiqueta")
        marcar(r"//[^\n]*|/\*.*?\*/", "comentario", re.S)


class Tarjeta(tk.Frame):
    """Indicador con un número grande (antes -> después) y su mejora."""

    def __init__(self, master, titulo):
        super().__init__(master, bg=SUPERFICIE, highlightbackground=BORDE,
                         highlightthickness=1, padx=12, pady=5)
        tk.Label(self, text=titulo, bg=SUPERFICIE, fg=TINTA_2, font=("Segoe UI", 9)).pack(anchor="w")
        fila = tk.Frame(self, bg=SUPERFICIE)
        fila.pack(anchor="w", fill="x")
        self.valor = tk.Label(fila, text="—", bg=SUPERFICIE, fg=TINTA, font=("Segoe UI Semibold", 15))
        self.valor.pack(side="left")
        self.delta = tk.Label(fila, text="", bg=SUPERFICIE, fg=MEJORA, font=("Segoe UI Semibold", 11))
        self.delta.pack(side="left", padx=(10, 0), pady=(6, 0))
        self.nota = tk.Label(self, text="", bg=SUPERFICIE, fg=TENUE, font=("Segoe UI", 8))
        self.nota.pack(anchor="w")

    def poner(self, valor, delta="", nota="", mejora=True):
        self.valor.configure(text=valor)
        self.delta.configure(text=delta, fg=MEJORA if mejora else EMPEORA)
        self.nota.configure(text=nota)


class GraficaBarras(tk.Canvas):
    """Barras horizontales agrupadas: sin optimizar vs optimizado, por tipo de operación."""

    def __init__(self, master):
        super().__init__(master, bg=SUPERFICIE, highlightthickness=0, height=180)
        self.datos = []
        self.bind("<Configure>", lambda e: self.dibujar())
        self.globo = None

    def poner(self, datos):
        self.datos = datos   # lista de (categoría, antes, después)
        self.dibujar()

    def dibujar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if not self.datos:
            self.create_text(w / 2, h / 2, text="Ejecuta ambas versiones para ver la comparación",
                             fill=TENUE, font=FUENTE_UI)
            return
        # leyenda (arriba, una fila)
        f9 = tkfont.Font(family="Segoe UI", size=9)
        lado = f9.metrics("linespace") * 0.7
        x, ym = 16, f9.metrics("linespace")
        for color, texto in ((SERIE_ANTES, "Sin optimizar"), (SERIE_DESPUES, "Optimizado")):
            self.create_rectangle(x, ym - lado / 2, x + lado, ym + lado / 2, fill=color, outline="")
            self.create_text(x + lado + 6, ym, text=texto, anchor="w", fill=TINTA_2, font=("Segoe UI", 9))
            x += lado + 6 + f9.measure(texto) + 24
        izq = 26 + max(f9.measure(c) for c, _, _ in self.datos)
        der = 20 + f9.measure(miles(max(max(a, d) for _, a, d in self.datos)))
        arriba = ym * 2 + 6
        maximo = max(max(a, d) for _, a, d in self.datos) or 1
        alto_fila = max(30, min(46, (h - arriba - 10) / len(self.datos)))
        barra = max(8, (alto_fila - 12) / 2)
        ancho = max(10, w - izq - der)
        # eje base
        self.create_line(izq, arriba - 4, izq, arriba + alto_fila * len(self.datos), fill=EJE)
        for k, (cat, a, d) in enumerate(self.datos):
            y0 = arriba + k * alto_fila + 4
            self.create_text(izq - 10, y0 + barra + 1, text=cat, anchor="e",
                             fill=TINTA_2, font=("Segoe UI", 9))
            for j, (valor, color, serie) in enumerate(((a, SERIE_ANTES, "Sin optimizar"),
                                                       (d, SERIE_DESPUES, "Optimizado"))):
                yb = y0 + j * (barra + 2)
                largo = ancho * valor / maximo
                if valor:
                    item = self.create_rectangle(izq + 1, yb, izq + 1 + largo, yb + barra,
                                                 fill=color, outline="")
                    texto = f"{cat} · {serie}: {miles(valor)}"
                    self.tag_bind(item, "<Enter>", lambda e, t=texto: self._mostrar_globo(e, t))
                    self.tag_bind(item, "<Leave>", lambda e: self._ocultar_globo())
                self.create_text(izq + largo + 8, yb + barra / 2, text=miles(valor), anchor="w",
                                 fill=TINTA if j else TINTA_2, font=("Segoe UI", 8))

    def _mostrar_globo(self, evento, texto):
        self._ocultar_globo()
        x, y = evento.x + 12, evento.y - 18
        t = self.create_text(x + 8, y, text=texto, anchor="w", fill="#ffffff", font=("Segoe UI", 9))
        x1, y1, x2, y2 = self.bbox(t)
        if x2 > self.winfo_width() - 4:
            self.move(t, -(x2 - x1) - 30, 0)
            x1, y1, x2, y2 = self.bbox(t)
        r = self.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4, fill=CABECERA, outline="")
        self.tag_raise(t, r)
        self.globo = (t, r)

    def _ocultar_globo(self):
        if self.globo:
            for i in self.globo:
                self.delete(i)
            self.globo = None


# =============================================================================
# Reporte del análisis del flujo de datos
# =============================================================================

def reporte_flujo(prog):
    seg = []

    def w(t, tag=None):
        seg.append((t, tag))

    cod = prog.codigo
    g = GFC(cod)
    nom = {i: f"d{k}" for k, i in enumerate((i for i, x in enumerate(cod) if definida(x)), 1)}

    def cj(s):
        return "{" + ", ".join(sorted((nom[d] for d in s), key=lambda t: int(t[1:]))) + "}" if s else "∅"

    def cv(s):
        return "{" + ", ".join(sorted(s)) + "}" if s else "∅"

    def nb(b):
        return f"B{b + 1}"

    def tabla(cabeza, filas):
        anchos = [max(len(str(x)) for x in col) + 3 for col in zip(cabeza, *filas)]
        w("   " + "".join(f"{c:<{a}}" for c, a in zip(cabeza, anchos)) + "\n", "cabeza")
        for f in filas:
            w("   " + "".join(f"{c:<{a}}" for c, a in zip(f, anchos)) + "\n")

    w("1. Bloques básicos y grafo de flujo de control (GFC)\n", "h1")
    w("   Bloque básico: instrucciones con una sola entrada y una sola salida.\n\n", "tenue")
    for b, idxs in enumerate(g.bloques):
        for k, i in enumerate(idxs):
            w(f"   {nb(b) if k == 0 else '':<6}", "bloque")
            w(f"{fmt(cod[i]):<32}")
            w(f"{nom.get(i, '')}\n", "tenue")
    aristas = ", ".join(f"{nb(b)}→{nb(s)}" for b in range(len(g.bloques)) for s in g.suc[b])
    w(f"\n   Aristas: {aristas or '(ninguna)'}\n")

    traza = []
    gen, kill, IN, OUT = defs_alcanzables(g, traza)
    w("\n2. Definiciones alcanzables  (hacia adelante · unión)\n", "h1")
    w("   OUT[B] = GEN[B] ∪ (IN[B] − KILL[B])        IN[B] = ∪ OUT[P]  para cada predecesor P\n", "tenue")
    w("   Se usa para PROPAGAR CONSTANTES y detectar variables sin inicializar.\n\n", "tenue")
    tabla(["Bloque", "GEN", "KILL", "IN", "OUT"],
          [[nb(b), cj(gen[b]), cj(kill[b]), cj(IN[b]), cj(OUT[b])] for b in range(len(g.bloques))])
    w(f"\n   Punto fijo alcanzado en {len(traza)} vueltas (en la última ya nada cambió).\n")
    for v, (ins, outs) in enumerate(traza, 1):
        w(f"   Vuelta {v}: ", "tenue")
        w("  ".join(f"{nb(b)}: IN={cj(ins[b])} OUT={cj(outs[b])}" for b in range(len(g.bloques))) + "\n", "tenue")

    use, df = use_def_bloques(g)
    _, ent, sal = vivas_por_instr(g)
    w("\n3. Variables vivas  (hacia atrás · unión)\n", "h1")
    w("   IN[B] = USE[B] ∪ (OUT[B] − DEF[B])         OUT[B] = ∪ IN[S]  para cada sucesor S\n", "tenue")
    w("   Se usa para ELIMINAR CÓDIGO MUERTO y decidir qué puede salir de un ciclo.\n\n", "tenue")
    tabla(["Bloque", "USE", "DEF", "IN (vivas al entrar)", "OUT (vivas al salir)"],
          [[nb(b), cv(use[b]), cv(df[b]), cv(ent[b]), cv(sal[b])] for b in range(len(g.bloques))])

    dom = dominadores(g)
    ciclos = ciclos_naturales(g, dom)
    w("\n4. Dominadores y ciclos  (hacia adelante · intersección)\n", "h1")
    w("   D domina a B si todo camino desde el inicio hasta B pasa por D.\n", "tenue")
    w("   Una arista B→H donde H domina a B es una arista de regreso: forma un ciclo.\n\n", "tenue")
    tabla(["Bloque", "Lo dominan"],
          [[nb(b), "{" + ", ".join(nb(x) for x in sorted(dom[b])) + "}"] for b in range(len(g.bloques))])
    w("\n")
    if ciclos:
        for h, cuerpo in sorted(ciclos.items()):
            primera = cod[g.bloques[h][0]]
            nombre = f" ({primera.etiqueta})" if primera.tipo == "etiqueta" else ""
            w(f"   Ciclo con encabezado {nb(h)}{nombre}: bloques "
              + "{" + ", ".join(nb(x) for x in sorted(cuerpo)) + "}\n", "bloque")
    else:
        w("   No hay ciclos.\n")

    w("\n5. Variables posiblemente sin inicializar\n", "h1")
    avisos = posibles_sin_inicializar(prog)
    if avisos:
        for i, u in avisos:
            w(f"   ⚠ '{u}' puede usarse sin valor en: {fmt(cod[i])}\n", "aviso")
    else:
        w("   Ninguna ✓\n")
    return seg


# =============================================================================
# Ventana principal
# =============================================================================

class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Optimizador de código — Lenguajes y Autómatas II")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(bg=FONDO)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass

        self.archivo = None
        self.lenguaje = tk.StringVar(value="c")
        self.activos = [tk.BooleanVar(value=True) for _ in PASOS]
        self.prog = self.opt = None
        self.registro = []
        self.entradas = {}
        self.valores_archivo = {}
        self.cola = queue.Queue()
        self._ocupado = False
        self.generacion = 0

        self._estilos()
        self._construir()
        self._cargar_lista_ejemplos()
        self.bind("<F5>", lambda e: self.optimizar())
        self.bind("<Control-o>", lambda e: self.abrir())
        self.bind("<Control-s>", lambda e: self.guardar())
        self.after(50, self._revisar_cola)

        inicial = os.path.join(CARPETA_EJEMPLOS, "07_procesa_exposicion.c")
        if os.path.exists(inicial):
            self.after(100, lambda: self.cargar_archivo(inicial))

    def px(self, n):
        """Convierte medidas pensadas a 96 ppp a la escala real de la pantalla."""
        return int(n * self.winfo_fpixels("1i") / 96)

    # ---- estilos -----------------------------------------------------------
    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", font=FUENTE_UI, background=FONDO, foreground=TINTA)
        s.configure("TFrame", background=FONDO)
        s.configure("Panel.TFrame", background=FONDO)
        s.configure("TLabel", background=FONDO, foreground=TINTA)
        s.configure("PanelTitulo.TLabel", font=("Segoe UI Semibold", 10), background=FONDO)
        s.configure("PanelInfo.TLabel", foreground=TINTA_2, background=FONDO, font=("Segoe UI", 9))
        s.configure("Tenue.TLabel", foreground=TENUE, background=FONDO, font=("Segoe UI", 9))
        s.configure("TButton", padding=(10, 5), background=SUPERFICIE, bordercolor=BORDE)
        s.map("TButton", background=[("active", "#eeede8")])
        s.configure("Primario.TButton", background=SERIE_ANTES, foreground="#ffffff",
                    font=("Segoe UI Semibold", 10), bordercolor=SERIE_ANTES)
        s.map("Primario.TButton", background=[("active", "#1f63b5"), ("disabled", "#9dbbe3")])
        s.configure("TCheckbutton", background=FONDO)
        s.configure("TRadiobutton", background=FONDO)
        s.configure("TNotebook", background=FONDO, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(14, 6), font=("Segoe UI", 10))
        s.map("TNotebook.Tab", background=[("selected", SUPERFICIE)], foreground=[("selected", TINTA)])
        alto_fila = int(tkfont.Font(family="Segoe UI", size=10).metrics("linespace") * 1.45)
        s.configure("Treeview", background=SUPERFICIE, fieldbackground=SUPERFICIE, rowheight=alto_fila,
                    bordercolor=BORDE, font=FUENTE_UI)
        s.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), background="#efeee9")
        s.map("Treeview", background=[("selected", FONDO_SELECCION)], foreground=[("selected", TINTA)])
        s.configure("TLabelframe", background=FONDO, bordercolor=BORDE)
        s.configure("TLabelframe.Label", background=FONDO, font=("Segoe UI Semibold", 10))
        s.configure("TPanedwindow", background=FONDO)

    # ---- construcción --------------------------------------------------------
    def _construir(self):
        cab = tk.Frame(self, bg=CABECERA, padx=18, pady=6)
        cab.pack(fill="x")
        tk.Label(cab, text="Optimizador de código", bg=CABECERA, fg="#ffffff",
                 font=("Segoe UI Semibold", 16)).pack(side="left")
        tk.Label(cab, text="   Criterios de mejora y análisis del flujo de datos · Lenguajes y Autómatas II · Equipo 3",
                 bg=CABECERA, fg="#b9c0cf", font=("Segoe UI", 10)).pack(side="left", pady=(5, 0))

        # barra de herramientas
        barra = ttk.Frame(self, padding=(14, 10, 14, 4))
        barra.pack(fill="x")
        ttk.Button(barra, text="📂 Abrir archivo…", command=self.abrir).pack(side="left")
        ttk.Label(barra, text="   Ejemplos:").pack(side="left")
        self.combo = ttk.Combobox(barra, state="readonly", width=34)
        self.combo.pack(side="left", padx=(4, 12))
        self.combo.bind("<<ComboboxSelected>>", self._elegir_ejemplo)
        self.boton_opt = ttk.Button(barra, text="▶  Optimizar  (F5)", style="Primario.TButton",
                                    command=self.optimizar)
        self.boton_opt.pack(side="left")
        ttk.Button(barra, text="💾 Guardar optimizado…", command=self.guardar).pack(side="left", padx=8)
        ttk.Label(barra, text="Lenguaje del archivo:").pack(side="left", padx=(18, 4))
        ttk.Radiobutton(barra, text="C", value="c", variable=self.lenguaje,
                        command=self._recolorear).pack(side="left")
        ttk.Radiobutton(barra, text="Tres direcciones", value="tac", variable=self.lenguaje,
                        command=self._recolorear).pack(side="left", padx=(6, 0))

        tecnicas = ttk.Frame(self, padding=(14, 2, 14, 6))
        tecnicas.pack(fill="x")
        ttk.Label(tecnicas, text="Técnicas activas:", style="PanelInfo.TLabel").pack(side="left", padx=(0, 6))
        for k, (nombre, _) in enumerate(PASOS):
            ttk.Checkbutton(tecnicas, text=f"{k + 1}. {nombre}", variable=self.activos[k],
                            command=self._cambio_tecnicas).pack(side="left", padx=(0, 10))

        # tarjetas resumen
        tarjetas = ttk.Frame(self, padding=(14, 2, 14, 8))
        tarjetas.pack(fill="x")
        self.t_codigo = Tarjeta(tarjetas, "Instrucciones en el código intermedio")
        self.t_ejec = Tarjeta(tarjetas, "Instrucciones ejecutadas (con los datos de entrada)")
        self.t_cambios = Tarjeta(tarjetas, "Transformaciones aplicadas")
        self.t_verif = Tarjeta(tarjetas, "¿Mismo resultado?")
        for t in (self.t_codigo, self.t_ejec, self.t_cambios, self.t_verif):
            t.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # zona principal: código arriba, pestañas abajo
        vertical = ttk.PanedWindow(self, orient="vertical")
        vertical.pack(fill="both", expand=True, padx=14, pady=(0, 4))
        arriba = ttk.PanedWindow(vertical, orient="horizontal")
        self.p_fuente = PanelCodigo(arriba, "① Archivo sin optimizar", editable=True)
        self.p_tac = PanelCodigo(arriba, "② Código intermedio (antes)")
        self.p_opt = PanelCodigo(arriba, "③ Código optimizado (después)")
        for p in (self.p_fuente, self.p_tac, self.p_opt):
            arriba.add(p, weight=1)
        self.p_fuente.texto.bind("<KeyRelease>", lambda e: self._programar_color())
        vertical.add(arriba, weight=3)

        self.notebook = ttk.Notebook(vertical)
        vertical.add(self.notebook, weight=2)
        self._pestana_pasos()
        self._pestana_ejecucion()
        self._pestana_flujo()

        self.estado = tk.Label(self, text="Listo.", anchor="w", bg="#efeee9", fg=TINTA_2,
                               font=("Segoe UI", 9), padx=14, pady=4)
        self.estado.pack(fill="x", side="bottom")

    def _pestana_pasos(self):
        marco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(marco, text="  Paso a paso  ")
        pan = ttk.PanedWindow(marco, orient="horizontal")
        pan.pack(fill="both", expand=True)
        izq = ttk.Frame(pan)
        self.arbol = ttk.Treeview(izq, columns=("cambios",), show="tree headings", selectmode="browse",
                                  height=6)
        self.arbol.heading("#0", text="Paso")
        self.arbol.heading("cambios", text="Cambios")
        self.arbol.column("#0", width=self.px(290))
        self.arbol.column("cambios", width=self.px(95), anchor="center")
        self.arbol.pack(fill="both", expand=True)
        self.arbol.bind("<<TreeviewSelect>>", self._seleccion_paso)
        pan.add(izq, weight=1)

        der = ttk.PanedWindow(pan, orient="horizontal")
        marco_c = ttk.Frame(der)
        ttk.Label(marco_c, text="Qué cambió en este paso", style="PanelTitulo.TLabel").pack(anchor="w", pady=(0, 4))
        self.txt_cambios = tk.Text(marco_c, wrap="word", bd=0, highlightthickness=1, height=6,
                                   highlightbackground=BORDE, bg=SUPERFICIE, fg=TINTA,
                                   font=FUENTE_COD, padx=10, pady=8, spacing3=4)
        self.txt_cambios.pack(fill="both", expand=True)
        self.txt_cambios.tag_configure("titulo", font=("Segoe UI Semibold", 12), spacing3=8)
        self.txt_cambios.tag_configure("tenue", foreground=TENUE, font=("Segoe UI", 10))
        self.txt_cambios.tag_configure("viñeta", foreground=TINTA_2)
        for k, c in enumerate(COLOR_PASO):
            self.txt_cambios.tag_configure(f"marca{k + 1}", foreground=c, font=("Segoe UI", 13))
        der.add(marco_c, weight=3)
        self.p_paso = PanelCodigo(der, "Código después de este paso")
        der.add(self.p_paso, weight=2)
        pan.add(der, weight=4)

    def _pestana_ejecucion(self):
        marco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(marco, text="  Ejecutar y comparar  ")
        izq = ttk.Labelframe(marco, text="Datos de entrada", padding=10)
        izq.pack(side="left", fill="y")
        self.marco_entradas = ttk.Frame(izq)
        self.marco_entradas.pack(fill="x")
        ttk.Label(izq, text="Arreglos: aleatorio(N), ceros(N) o 1, 2, 3",
                  style="Tenue.TLabel").pack(anchor="w", pady=(6, 10))
        self.boton_ejec = ttk.Button(izq, text="▶  Ejecutar ambas versiones",
                                     style="Primario.TButton", command=self.ejecutar_ambas)
        self.boton_ejec.pack(fill="x")
        self.boton_verif = ttk.Button(izq, text="✓  Verificar con 300 entradas aleatorias",
                                      command=self.verificar)
        self.boton_verif.pack(fill="x", pady=(6, 0))
        self.lbl_resultado = tk.Label(izq, text="", justify="left", anchor="w", bg=FONDO, fg=TINTA,
                                      font=("Segoe UI", 9), wraplength=self.px(300))
        self.lbl_resultado.pack(fill="x", pady=(12, 0))

        der = ttk.Frame(marco, padding=(12, 0, 0, 0))
        der.pack(side="left", fill="both", expand=True)
        cols = ("antes", "despues", "ahorro", "pct")
        self.tabla = ttk.Treeview(der, columns=cols, show="tree headings", height=6)
        self.tabla.heading("#0", text="Operación")
        for c, t in zip(cols, ("Sin optimizar", "Optimizado", "Diferencia", "%")):
            self.tabla.heading(c, text=t)
            self.tabla.column(c, width=self.px(105), anchor="e")
        self.tabla.column("#0", width=self.px(185))
        self.tabla.tag_configure("total", font=("Segoe UI Semibold", 10))
        self.tabla.pack(side="left", fill="y")
        marco_g = ttk.Frame(der, padding=(12, 0, 0, 0))
        marco_g.pack(side="left", fill="both", expand=True)
        ttk.Label(marco_g, text="Operaciones ejecutadas por tipo",
                  style="PanelTitulo.TLabel").pack(anchor="w")
        self.grafica = GraficaBarras(marco_g)
        self.grafica.pack(fill="both", expand=True, pady=(4, 0))

    def _pestana_flujo(self):
        marco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(marco, text="  Análisis del flujo de datos  ")
        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(0, 6))
        ttk.Label(fila, text="Analizar:").pack(side="left")
        self.flujo_de = tk.StringVar(value="antes")
        ttk.Radiobutton(fila, text="Código intermedio (antes)", value="antes", variable=self.flujo_de,
                        command=self._mostrar_flujo).pack(side="left", padx=8)
        ttk.Radiobutton(fila, text="Código optimizado (después)", value="despues", variable=self.flujo_de,
                        command=self._mostrar_flujo).pack(side="left")
        cuerpo = tk.Frame(marco, bg=BORDE, padx=1, pady=1)
        cuerpo.pack(fill="both", expand=True)
        self.txt_flujo = tk.Text(cuerpo, wrap="none", bd=0, highlightthickness=0, bg=SUPERFICIE, height=6,
                                 fg=TINTA, font=("Consolas", 10), padx=10, pady=8)
        sy = ttk.Scrollbar(cuerpo, orient="vertical", command=self.txt_flujo.yview)
        sx = ttk.Scrollbar(cuerpo, orient="horizontal", command=self.txt_flujo.xview)
        self.txt_flujo.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        self.txt_flujo.pack(fill="both", expand=True)
        self.txt_flujo.tag_configure("h1", font=("Segoe UI Semibold", 12), spacing1=6, spacing3=4)
        self.txt_flujo.tag_configure("tenue", foreground=TENUE)
        self.txt_flujo.tag_configure("cabeza", foreground=TINTA_2, font=("Consolas", 10, "bold"))
        self.txt_flujo.tag_configure("bloque", foreground="#0d5c9e", font=("Consolas", 10, "bold"))
        self.txt_flujo.tag_configure("aviso", foreground=EMPEORA)

    # ---- archivos ------------------------------------------------------------
    def _cargar_lista_ejemplos(self):
        archivos = sorted(glob.glob(os.path.join(CARPETA_EJEMPLOS, "*.c"))
                          + glob.glob(os.path.join(CARPETA_EJEMPLOS, "*.tac")))
        self.ejemplos = {os.path.basename(a): a for a in archivos}
        self.combo["values"] = list(self.ejemplos)

    def _elegir_ejemplo(self, _=None):
        nombre = self.combo.get()
        if nombre in self.ejemplos:
            self.cargar_archivo(self.ejemplos[nombre])

    def abrir(self):
        ruta = filedialog.askopenfilename(
            title="Abrir archivo sin optimizar", initialdir=CARPETA_EJEMPLOS,
            filetypes=[("Código C o de tres direcciones", "*.c *.tac *.txt"),
                       ("Código C", "*.c"), ("Tres direcciones", "*.tac"), ("Todos", "*.*")])
        if ruta:
            self.cargar_archivo(ruta)

    def cargar_archivo(self, ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                contenido = f.read()
        except UnicodeDecodeError:
            with open(ruta, encoding="latin-1") as f:
                contenido = f.read()
        except OSError as e:
            messagebox.showerror("No se pudo abrir", str(e))
            return
        self.archivo = ruta
        nombre = os.path.basename(ruta)
        self.combo.set(nombre if nombre in self.ejemplos else "")
        self.lenguaje.set("tac" if ruta.lower().endswith((".tac", ".txt")) else "c")
        self.p_fuente.poner(contenido)
        self.p_fuente.info.configure(text=nombre)
        self._recolorear()
        self.entradas = {}
        self.optimizar()

    def guardar(self):
        if not self.opt:
            messagebox.showinfo("Nada que guardar", "Primero optimiza un programa.")
            return
        base = os.path.splitext(os.path.basename(self.archivo or "programa"))[0]
        ruta = filedialog.asksaveasfilename(
            title="Guardar código optimizado", initialfile=f"{base}_optimizado.tac",
            defaultextension=".tac", filetypes=[("Tres direcciones", "*.tac"), ("Texto", "*.txt")])
        if not ruta:
            return
        activos = [PASOS[k][0] for k, v in enumerate(self.activos) if v.get()]
        entrada = ", ".join(f"{n}={e.get()}" for n, e in self.entradas.items())
        cabecera = [
            f"// Código optimizado a partir de: {os.path.basename(self.archivo or '(texto)')}",
            f"// Técnicas: {', '.join(activos)}",
            f"// Instrucciones: {contar_instrucciones(self.prog.codigo)} -> {contar_instrucciones(self.opt.codigo)}",
        ]
        if entrada:
            cabecera.append(f"// @entrada: {entrada}")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\n".join(cabecera) + "\n\n" + "\n".join(listado(self.opt.codigo)) + "\n")
        self._estado(f"Guardado en {ruta}")

    # ---- optimización --------------------------------------------------------
    def _cambio_tecnicas(self):
        if self.prog is not None:
            self.optimizar()

    def optimizar(self):
        texto = self.p_fuente.obtener()
        self.p_fuente.limpiar_resaltado("error")
        try:
            if self.lenguaje.get() == "c":
                prog = compilar_c(texto)
            else:
                prog = programa_desde_tac(texto, os.path.splitext(os.path.basename(self.archivo or "programa"))[0])
        except (ErrorC, SyntaxError) as e:
            msg = str(e)
            m = re.search(r"Línea (\d+)", msg)
            if m:
                self.p_fuente.resaltar([int(m[1])], "error")
                self.p_fuente.texto.see(f"{m[1]}.0")
            self._estado(f"Error: {msg}", error=True)
            return
        activos = [k + 1 for k, v in enumerate(self.activos) if v.get()]
        self.generacion += 1          # invalida resultados de ejecuciones anteriores
        self.prog = prog
        self.opt, self.registro = optimizar_registro(prog, activos)
        self.valores_archivo = leer_entrada(texto)

        antes, despues = listado(prog.codigo), listado(self.opt.codigo)
        self.p_tac.poner("\n".join(antes))
        self.p_opt.poner("\n".join(despues))
        self.p_tac.colorear("tac")
        self.p_opt.colorear("tac")
        quitadas, nuevas = self._diferencias(antes, despues)
        self.p_tac.resaltar(quitadas, "quitada")
        self.p_opt.resaltar(nuevas, "nueva")
        n1, n2 = contar_instrucciones(prog.codigo), contar_instrucciones(self.opt.codigo)
        self.p_tac.info.configure(text=f"{n1} instrucciones · {len(quitadas)} líneas cambian o se van")
        self.p_opt.info.configure(text=f"{n2} instrucciones · {len(nuevas)} líneas nuevas o cambiadas")

        total_cambios = sum(len(p.cambios) for p in self.registro)
        rondas = self.registro[-1].ronda if self.registro else 0
        if n1 == n2:
            self.t_codigo.poner(f"{n1} → {n2}", "", "mismo tamaño: el código se reacomodó "
                                "(compara las instrucciones ejecutadas)")
        else:
            self.t_codigo.poner(f"{n1} → {n2}", self._pct(n1, n2), "líneas del código de tres direcciones",
                                mejora=n2 < n1)
        usadas = sorted({p.numero for p in self.registro if p.cambios})
        self.t_cambios.poner(str(total_cambios), "",
                             f"{len(usadas)} técnicas aplicaron cambios · punto fijo en {rondas} rondas")
        self.t_ejec.poner("…", "", "ejecutando…")
        self.t_verif.poner("…", "", "verificando…")

        self._llenar_pasos()
        self._llenar_entradas()
        self._mostrar_flujo()
        self._estado(f"Optimizado: {n1} → {n2} instrucciones, {total_cambios} transformaciones.")
        self.ejecutar_ambas(automatico=True)

    @staticmethod
    def _pct(a, b):
        if not a or a == b:
            return "sin cambio" if a == b else ""
        p = 100 * (a - b) / a
        return f"−{p:.0f}%" if p > 0 else f"+{-p:.0f}%"

    @staticmethod
    def _diferencias(antes, despues):
        a = [l.strip() for l in antes]
        b = [l.strip() for l in despues]
        quitadas, nuevas = [], []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op in ("replace", "delete"):
                quitadas += range(i1 + 1, i2 + 1)
            if op in ("replace", "insert"):
                nuevas += range(j1 + 1, j2 + 1)
        return quitadas, nuevas

    # ---- paso a paso ---------------------------------------------------------
    def _llenar_pasos(self):
        self.arbol.delete(*self.arbol.get_children())
        self.arbol.insert("", "end", iid="orig", text="  Código intermedio original", values=("",))
        ronda_nodo = None
        ronda_actual = 0
        for k, p in enumerate(self.registro):
            if p.ronda != ronda_actual:
                ronda_actual = p.ronda
                hay = any(q.cambios for q in self.registro if q.ronda == ronda_actual)
                texto = f"  Ronda {ronda_actual}" + ("" if hay else "  (nada cambió → punto fijo)")
                ronda_nodo = self.arbol.insert("", "end", iid=f"r{ronda_actual}", text=texto, open=True)
            if p.cambios:
                self.arbol.insert(ronda_nodo, "end", iid=f"p{k}", text=f"  {p.numero}. {p.nombre}",
                                  values=(len(p.cambios),), tags=(f"paso{p.numero}",))
        self.arbol.insert("", "end", iid="final", text="  Resultado final", values=("",))
        primero = next((f"p{k}" for k, p in enumerate(self.registro) if p.cambios), "orig")
        self.arbol.selection_set(primero)
        self.arbol.see(primero)

    def _seleccion_paso(self, _=None):
        sel = self.arbol.selection()
        if not sel:
            return
        iid = sel[0]
        t = self.txt_cambios
        t.configure(state="normal")
        t.delete("1.0", "end")
        if iid == "orig" or iid.startswith("r"):
            previo = actual = self.prog.codigo
            t.insert("end", "Código intermedio sin optimizar\n", "titulo")
            t.insert("end", "Así lo generó el traductor, instrucción por instrucción. "
                            "Selecciona un paso de la lista para ver qué transformó cada técnica.", "tenue")
        elif iid == "final":
            previo, actual = self.prog.codigo, self.opt.codigo
            n1, n2 = contar_instrucciones(previo), contar_instrucciones(actual)
            t.insert("end", "Resultado final\n", "titulo")
            t.insert("end", f"{n1} → {n2} instrucciones en el código. "
                            "Verde: líneas nuevas o cambiadas respecto al original.\n\n", "tenue")
            for p in self.registro:
                if p.cambios:
                    t.insert("end", "■ ", f"marca{p.numero}")
                    t.insert("end", f"{p.nombre}: {len(p.cambios)} cambio(s)\n")
        else:
            k = int(iid[1:])
            p = self.registro[k]
            previo = self.registro[k - 1].codigo if k > 0 else self.prog.codigo
            actual = p.codigo
            t.insert("end", "■ ", f"marca{p.numero}")
            t.insert("end", f"Paso {p.numero} · {p.nombre}  (ronda {p.ronda})\n", "titulo")
            for c in p.cambios:
                t.insert("end", "• ", "viñeta")
                t.insert("end", c + "\n")
        t.configure(state="disabled")
        lineas = listado(actual)
        self.p_paso.poner("\n".join(lineas))
        self.p_paso.colorear("tac")
        _, nuevas = self._diferencias(listado(previo), lineas)
        self.p_paso.resaltar(nuevas, "nueva")
        self.p_paso.info.configure(text=f"{contar_instrucciones(actual)} instrucciones")

    # ---- ejecución -----------------------------------------------------------
    def _llenar_entradas(self):
        anteriores = {n: e.get() for n, e in self.entradas.items()}
        for w in self.marco_entradas.winfo_children():
            w.destroy()
        self.entradas = {}
        if not self.prog.params:
            ttk.Label(self.marco_entradas, text="Este programa no recibe parámetros.",
                      style="Tenue.TLabel").pack(anchor="w")
        for p in self.prog.params:
            fila = ttk.Frame(self.marco_entradas)
            fila.pack(fill="x", pady=2)
            tipo = ("float" if p.flotante else "int") + ("[ ]" if p.arreglo else "")
            ttk.Label(fila, text=f"{p.nombre}", width=10, font=("Consolas", 10, "bold")).pack(side="left")
            ttk.Label(fila, text=tipo, width=8, style="Tenue.TLabel").pack(side="left")
            e = ttk.Entry(fila, width=22, font=("Consolas", 10))
            e.pack(side="left", fill="x", expand=True)
            defecto = "aleatorio(10)" if p.arreglo else "10"
            e.insert(0, anteriores.get(p.nombre) or self.valores_archivo.get(p.nombre, defecto))
            e.bind("<Return>", lambda ev: self.ejecutar_ambas())
            self.entradas[p.nombre] = e

    def _datos(self):
        args, arr = {}, {}
        for p in self.prog.params:
            v = valor_entrada(self.entradas[p.nombre].get(), p)
            (arr if p.arreglo else args)[p.nombre] = v
        return args, arr

    def ejecutar_ambas(self, automatico=False):
        if self.prog is None:
            return
        if self._ocupado:
            if automatico:   # termina lo anterior y vuelve a intentar con el programa nuevo
                self.after(150, lambda: self.ejecutar_ambas(automatico=True))
            return
        try:
            args, arr = self._datos()
        except ValueError as e:
            self.t_ejec.poner("—", "", "revisa los datos de entrada")
            self._estado(f"Datos de entrada: {e}", error=True)
            return
        prog, opt = self.prog, self.opt

        def trabajo():
            res = []
            for p in (prog, opt):
                t0 = time.perf_counter()
                try:
                    r = ejecutar(p, args, arr)
                    res.append((r, time.perf_counter() - t0, None))
                except ErrorEjecucion as e:
                    res.append((None, 0, str(e)))
            return res

        self._en_segundo_plano(trabajo, lambda res: self._mostrar_ejecucion(res, automatico))

    def _mostrar_ejecucion(self, res, automatico):
        (r1, s1, e1), (r2, s2, e2) = res
        self.tabla.delete(*self.tabla.get_children())
        if e1 or e2:
            msg = f"Sin optimizar: {e1 or 'ok'}\nOptimizado: {e2 or 'ok'}"
            self.lbl_resultado.configure(text="⚠ Error al ejecutar\n" + msg, fg=EMPEORA)
            self.t_ejec.poner("—", "", "error al ejecutar: revisa los datos")
            self.grafica.poner([])
            self._estado("Error al ejecutar: " + (e1 or e2), error=True)
            if automatico:
                self.verificar()
            return
        c1, c2 = r1.contador, r2.contador
        datos = []
        for cat in ORDEN_CAT:
            a, d = c1[cat], c2[cat]
            if not (a or d):
                continue
            dif = d - a
            pct = (f"{100 * dif / a:+.0f}%" if dif else "0%") if a else ""
            tags = ("total",) if cat == "instrucciones totales" else ()
            self.tabla.insert("", "end", text=f"  {cat}", tags=tags,
                              values=(miles(a), miles(d), f"{dif:+,}".replace(",", " ") if dif else "0", pct))
            if cat != "instrucciones totales":
                datos.append((cat, a, d))
        self.grafica.poner(datos)
        a, d = c1["instrucciones totales"], c2["instrucciones totales"]
        self.t_ejec.poner(f"{miles(a)} → {miles(d)}", self._pct(a, d),
                          f"tiempo de interpretación: {s1 * 1000:.1f} ms → {s2 * 1000:.1f} ms", mejora=d <= a)
        igual = (r1.valor, r1.salida, r1.memoria) == (r2.valor, r2.salida, r2.memoria)
        lineas = [f"Valor devuelto:  {r1.valor}  /  {r2.valor}"]
        if r1.salida or r2.salida:
            lineas.append(f"Salida (printf): {len(r1.salida)} / {len(r2.salida)} valores")
        if r1.memoria:
            lineas.append("Arreglos al terminar: " + ("iguales" if r1.memoria == r2.memoria else "DIFERENTES"))
        lineas.append(("✓ Ambas versiones dan el mismo resultado." if igual
                       else "✗ ¡Los resultados son diferentes!"))
        self.lbl_resultado.configure(text="\n".join(lineas), fg=MEJORA if igual else EMPEORA)
        self._estado(f"Ejecutado: {miles(a)} → {miles(d)} instrucciones ({self._pct(a, d)}).")
        if automatico:
            self.verificar()

    def verificar(self):
        if self.prog is None or self._ocupado:
            return
        prog, opt = self.prog, self.opt
        self.t_verif.poner("…", "", "probando 300 entradas aleatorias…")
        self._en_segundo_plano(lambda: verificar_aleatorio(prog, opt, 300),
                               self._mostrar_verificacion)

    def _mostrar_verificacion(self, res):
        iguales, validas, contra = res
        if contra is None:
            self.t_verif.poner("✓ Sí", f"{iguales}/{iguales}",
                               f"entradas aleatorias con el mismo resultado ({validas} sin error)")
        else:
            self.t_verif.poner("✗ No", "", f"diferencia con {contra}", mejora=False)
            self._estado(f"La verificación encontró una diferencia con {contra}", error=True)

    # ---- flujo de datos ------------------------------------------------------
    def _mostrar_flujo(self):
        prog = self.prog if self.flujo_de.get() == "antes" else self.opt
        t = self.txt_flujo
        t.configure(state="normal")
        t.delete("1.0", "end")
        if prog is not None:
            for texto, tag in reporte_flujo(prog):
                t.insert("end", texto, tag or ())
        t.configure(state="disabled")

    # ---- utilidades ----------------------------------------------------------
    def _en_segundo_plano(self, funcion, al_terminar):
        self._ocupado = True
        for b in (self.boton_ejec, self.boton_verif, self.boton_opt):
            b.state(["disabled"])
        generacion = self.generacion
        destino = al_terminar

        def al_terminar(res):
            if generacion == self.generacion:   # si el programa cambió, el resultado ya no aplica
                destino(res)

        def hilo():
            try:
                self.cola.put((al_terminar, funcion(), None))
            except Exception as e:  # noqa: BLE001 — se muestra en la barra de estado
                self.cola.put((al_terminar, None, e))
        threading.Thread(target=hilo, daemon=True).start()

    def _revisar_cola(self):
        try:
            while True:
                al_terminar, res, error = self.cola.get_nowait()
                self._ocupado = False
                for b in (self.boton_ejec, self.boton_verif, self.boton_opt):
                    b.state(["!disabled"])
                if error:
                    self._estado(f"Error: {error}", error=True)
                else:
                    al_terminar(res)
        except queue.Empty:
            pass
        self.after(50, self._revisar_cola)

    def _programar_color(self):
        if getattr(self, "_id_color", None):
            self.after_cancel(self._id_color)
        self._id_color = self.after(300, self._recolorear)

    def _recolorear(self):
        self.p_fuente.colorear(self.lenguaje.get())

    def _estado(self, texto, error=False):
        self.estado.configure(text=texto, fg=EMPEORA if error else TINTA_2)


def activar_dpi():
    """Texto nítido en pantallas con escala (125 %, 150 %...) en Windows."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


if __name__ == "__main__":
    activar_dpi()
    Aplicacion().mainloop()
