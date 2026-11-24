# -*- coding: utf-8 -*-
"""
Núcleo del optimizador (lo usan la interfaz gráfica y la demo de consola).

Trabaja sobre CÓDIGO DE TRES DIRECCIONES y aplica, en el orden de la
exposición, seis optimizaciones decididas con análisis del flujo de datos:

    1. Plegado de constantes          4. Subexpresiones comunes
    2. Propagación de constantes      5. Código invariante en ciclos
    3. Eliminación de código muerto   6. Reducción de intensidad

Análisis implementados (todos con el mismo motor iterativo de punto fijo):
    - Definiciones alcanzables  (hacia adelante, unión)
    - Variables vivas           (hacia atrás,   unión)
    - Dominadores               (hacia adelante, intersección)
"""

import math
import operator
import re
from collections import Counter
from dataclasses import dataclass, field, replace


# =============================================================================
# 1. Representación: código de tres direcciones
# =============================================================================

@dataclass
class Instr:
    tipo: str                # asignar | op | cargar | guardar | si | ir | etiqueta | imprimir | retornar
    dst: str | None = None   # variable que se define
    a: object = None         # operando (nombre de variable o constante)
    op: str | None = None    # operador
    b: object = None         # segundo operando
    arr: str | None = None   # arreglo (para cargar/guardar)
    etiqueta: str | None = None   # destino de salto / texto de printf


@dataclass
class Param:
    nombre: str
    arreglo: bool = False
    flotante: bool = False


@dataclass
class Programa:
    nombre: str
    codigo: list
    params: list = field(default_factory=list)        # lista de Param
    flotantes: set = field(default_factory=set)       # variables/arreglos declarados float
    locales: dict = field(default_factory=dict)       # arreglos locales: nombre -> tamaño


def _div_c(a, b):
    """División como en C: entera trunca hacia cero."""
    if isinstance(a, int) and isinstance(b, int):
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b >= 0) else -q
    return a / b


def _mod_c(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a - b * _div_c(a, b)
    return math.fmod(a, b)


OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul,
       "<<": operator.lshift, ">>": operator.rshift, "/": _div_c, "%": _mod_c}
PURAS = {"+", "-", "*", "<<", ">>"}   # no pueden fallar: se pueden mover o reutilizar
REL = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
       ">=": operator.ge, "==": operator.eq, "!=": operator.ne}
INVERSA = {"<": ">=", ">=": "<", ">": "<=", "<=": ">", "==": "!=", "!=": "=="}
CONMUTATIVAS = {"+", "*"}

CAMPOS_USO = {"asignar": ("a",), "op": ("a", "b"), "cargar": ("a",),
              "guardar": ("a", "b"), "si": ("a", "b"), "imprimir": ("a",),
              "retornar": ("a",)}


def es_const(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def definida(ins):
    return ins.dst if ins.tipo in ("asignar", "op", "cargar") else None


def usadas(ins):
    return [getattr(ins, c) for c in CAMPOS_USO.get(ins.tipo, ())
            if isinstance(getattr(ins, c), str)]


def copiar(codigo):
    return [replace(i) for i in codigo]


def _operando(t):
    for conv in (int, float):
        try:
            return conv(t)
        except ValueError:
            pass
    return t


def parsear(texto):
    """Texto de tres direcciones -> lista de Instr."""
    codigo = []
    for num, linea in enumerate(texto.splitlines(), 1):
        s = linea.split("//")[0].strip()
        if not s:
            continue
        if m := re.fullmatch(r"(\w+):", s):
            codigo.append(Instr("etiqueta", etiqueta=m[1]))
        elif m := re.fullmatch(r"goto (\w+)", s):
            codigo.append(Instr("ir", etiqueta=m[1]))
        elif m := re.fullmatch(r"if (\S+) (\S+) (\S+) goto (\w+)", s):
            codigo.append(Instr("si", a=_operando(m[1]), op=m[2], b=_operando(m[3]), etiqueta=m[4]))
        elif m := re.fullmatch(r"return(?: (\S+))?", s):
            codigo.append(Instr("retornar", a=_operando(m[1]) if m[1] else None))
        elif m := re.fullmatch(r'print (".*")', s):
            codigo.append(Instr("imprimir", etiqueta=m[1][1:-1]))
        elif m := re.fullmatch(r"print (\S+)", s):
            codigo.append(Instr("imprimir", a=_operando(m[1])))
        elif m := re.fullmatch(r"(\w+)\[(\S+)\] = (\S+)", s):
            codigo.append(Instr("guardar", arr=m[1], a=_operando(m[2]), b=_operando(m[3])))
        elif m := re.fullmatch(r"(\w+) = (\w+)\[(\S+)\]", s):
            codigo.append(Instr("cargar", dst=m[1], arr=m[2], a=_operando(m[3])))
        elif m := re.fullmatch(r"(\w+) = (\S+) (\S+) (\S+)", s):
            if m[3] not in OPS:
                raise SyntaxError(f"Línea {num}: operador '{m[3]}' no soportado")
            codigo.append(Instr("op", dst=m[1], a=_operando(m[2]), op=m[3], b=_operando(m[4])))
        elif m := re.fullmatch(r"(\w+) = (\S+)", s):
            codigo.append(Instr("asignar", dst=m[1], a=_operando(m[2])))
        else:
            raise SyntaxError(f"Línea {num}: no entiendo {linea.strip()!r}")
    etiquetas = {i.etiqueta for i in codigo if i.tipo == "etiqueta"}
    for i in codigo:
        if i.tipo in ("si", "ir") and i.etiqueta not in etiquetas:
            raise SyntaxError(f"La etiqueta {i.etiqueta} no está definida")
    if not codigo or codigo[-1].tipo != "retornar":
        codigo.append(Instr("retornar"))
    return codigo


def programa_desde_tac(texto, nombre="programa"):
    """Crea un Programa a partir de texto de tres direcciones.
    Los parámetros se deducen: variables que se usan sin haberse definido."""
    codigo = parsear(texto)
    definidas = {definida(i) for i in codigo if definida(i)}
    arreglos = list(dict.fromkeys(i.arr for i in codigo if i.tipo in ("cargar", "guardar")))
    escalares = list(dict.fromkeys(u for i in codigo for u in usadas(i) if u not in definidas))
    params = [Param(e) for e in escalares] + [Param(a, arreglo=True) for a in arreglos]
    return Programa(nombre, codigo, params)


def fmt(ins):
    t = ins.tipo
    if t == "etiqueta":
        return f"{ins.etiqueta}:"
    if t == "asignar":
        return f"{ins.dst} = {ins.a}"
    if t == "op":
        return f"{ins.dst} = {ins.a} {ins.op} {ins.b}"
    if t == "cargar":
        return f"{ins.dst} = {ins.arr}[{ins.a}]"
    if t == "guardar":
        return f"{ins.arr}[{ins.a}] = {ins.b}"
    if t == "si":
        return f"if {ins.a} {ins.op} {ins.b} goto {ins.etiqueta}"
    if t == "ir":
        return f"goto {ins.etiqueta}"
    if t == "imprimir":
        return f'print "{ins.etiqueta}"' if ins.a is None else f"print {ins.a}"
    if t == "retornar":
        return "return" if ins.a is None else f"return {ins.a}"
    return "?"


def listado(codigo):
    return [fmt(i) if i.tipo == "etiqueta" else "    " + fmt(i) for i in codigo]


def contar_instrucciones(codigo):
    return sum(1 for i in codigo if i.tipo != "etiqueta")


# =============================================================================
# 2. Grafo de flujo de control (bloques básicos)
# =============================================================================

class GFC:
    def __init__(self, codigo):
        self.codigo = codigo
        n = len(codigo)
        lideres = {0} if codigo else set()
        for i, ins in enumerate(codigo):
            if ins.tipo == "etiqueta":
                lideres.add(i)
            if ins.tipo in ("si", "ir", "retornar") and i + 1 < n:
                lideres.add(i + 1)
        lideres = sorted(lideres)
        self.bloques = [list(range(s, e)) for s, e in zip(lideres, lideres[1:] + [n])]
        self.bloque_de = {i: b for b, idxs in enumerate(self.bloques) for i in idxs}
        etiq = {ins.etiqueta: self.bloque_de[i]
                for i, ins in enumerate(codigo) if ins.tipo == "etiqueta"}
        nb = len(self.bloques)
        self.suc = []
        for b, idxs in enumerate(self.bloques):
            ult = codigo[idxs[-1]]
            sig = [b + 1] if b + 1 < nb else []
            if ult.tipo == "ir":
                s = [etiq[ult.etiqueta]]
            elif ult.tipo == "si":
                s = [etiq[ult.etiqueta]] + sig
            elif ult.tipo == "retornar":
                s = []
            else:
                s = sig
            self.suc.append(list(dict.fromkeys(s)))
        self.pred = [[] for _ in range(nb)]
        for b, ss in enumerate(self.suc):
            for s in ss:
                self.pred[s].append(b)


def alcanzables(g):
    if not g.bloques:
        return set()
    vistos, pila = {0}, [0]
    while pila:
        for s in g.suc[pila.pop()]:
            if s not in vistos:
                vistos.add(s)
                pila.append(s)
    return vistos


# =============================================================================
# 3. Motor genérico de análisis del flujo de datos (iteración hasta punto fijo)
#    adelante:  IN[B]  = ∪/∩ OUT[P]    OUT[B] = GEN[B] ∪ (IN[B] − KILL[B])
#    atrás:     OUT[B] = ∪/∩ IN[S]     IN[B]  = USE[B] ∪ (OUT[B] − DEF[B])
# =============================================================================

def flujo_de_datos(g, gen, kill, adelante=True, union=True, universo=None, traza=None):
    n = len(g.bloques)
    vecinos = g.pred if adelante else g.suc
    inicial = set() if union else set(universo)
    entra = [set() for _ in range(n)]
    sale = [set(inicial) for _ in range(n)]
    orden = list(range(n)) if adelante else list(reversed(range(n)))
    cambio = True
    while cambio:
        cambio = False
        for b in orden:
            vs = vecinos[b]
            if (adelante and b == 0 and not union) or not vs:
                nuevo_entra = set()
            elif union:
                nuevo_entra = set().union(*(sale[p] for p in vs))
            else:
                nuevo_entra = set.intersection(*(sale[p] for p in vs))
            nuevo_sale = gen[b] | (nuevo_entra - kill[b])
            if nuevo_entra != entra[b] or nuevo_sale != sale[b]:
                cambio = True
            entra[b], sale[b] = nuevo_entra, nuevo_sale
        if traza is not None:
            traza.append(([set(x) for x in entra], [set(x) for x in sale]))
    return entra, sale


def defs_alcanzables(g, traza=None):
    codigo = g.codigo
    defs_de = {}
    for i, ins in enumerate(codigo):
        if v := definida(ins):
            defs_de.setdefault(v, set()).add(i)
    gen, kill = [], []
    for idxs in g.bloques:
        G, K = set(), set()
        for i in idxs:
            if v := definida(codigo[i]):
                G -= defs_de[v]
                G.add(i)
                K |= defs_de[v] - {i}
        gen.append(G)
        kill.append(K - G)
    IN, OUT = flujo_de_datos(g, gen, kill, adelante=True, union=True, traza=traza)
    return gen, kill, IN, OUT


def alcanzan_por_instr(g, IN):
    codigo, res = g.codigo, {}
    for b, idxs in enumerate(g.bloques):
        cur = set(IN[b])
        for i in idxs:
            res[i] = set(cur)
            if v := definida(codigo[i]):
                cur = {d for d in cur if definida(codigo[d]) != v} | {i}
    return res


def use_def_bloques(g):
    codigo = g.codigo
    use, df = [], []
    for idxs in g.bloques:
        U, D = set(), set()
        for i in idxs:
            U |= {u for u in usadas(codigo[i]) if u not in D}
            if v := definida(codigo[i]):
                D.add(v)
        use.append(U)
        df.append(D)
    return use, df


def vivas_por_instr(g):
    """(vivas después de cada instrucción, vivas al entrar a cada bloque, vivas al salir)."""
    codigo = g.codigo
    use, df = use_def_bloques(g)
    al_salir, al_entrar = flujo_de_datos(g, use, df, adelante=False, union=True)
    despues = {}
    for b, idxs in enumerate(g.bloques):
        cur = set(al_salir[b])
        for i in reversed(idxs):
            despues[i] = set(cur)
            if v := definida(codigo[i]):
                cur.discard(v)
            cur |= set(usadas(codigo[i]))
    return despues, al_entrar, al_salir


def dominadores(g):
    n = len(g.bloques)
    gen = [{b} for b in range(n)]
    kill = [set() for _ in range(n)]
    _, OUT = flujo_de_datos(g, gen, kill, adelante=True, union=False, universo=range(n))
    return OUT


def ciclos_naturales(g, dom):
    ciclos = {}
    for b in range(len(g.bloques)):
        for h in g.suc[b]:
            if h in dom[b]:
                cuerpo, pila = {h, b}, [b]
                while pila:
                    x = pila.pop()
                    if x == h:
                        continue
                    for p in g.pred[x]:
                        if p not in cuerpo:
                            cuerpo.add(p)
                            pila.append(p)
                ciclos.setdefault(h, set()).update(cuerpo)
    return ciclos


def posibles_sin_inicializar(prog):
    """Usos de variables a los que puede llegar 'ninguna definición'
    (definiciones alcanzables con una definición ficticia al inicio)."""
    codigo = prog.codigo
    params = {p.nombre for p in prog.params}
    variables = sorted({u for i in codigo for u in usadas(i)} - params)
    ficticias = [Instr("asignar", dst=v, a=None) for v in variables]
    ext = ficticias + list(codigo)
    g = GFC(ext)
    _, _, IN, _ = defs_alcanzables(g)
    rd = alcanzan_por_instr(g, IN)
    avisos = []
    k = len(ficticias)
    for i in range(k, len(ext)):
        for u in usadas(ext[i]):
            if any(d < k and ext[d].dst == u for d in rd[i]):
                avisos.append((i - k, u))
    return avisos


# =============================================================================
# 4. Las seis optimizaciones: cada una devuelve (código nuevo, cambios)
# =============================================================================

def plegar(ins):
    if ins.tipo == "op" and es_const(ins.a) and es_const(ins.b):
        if ins.op in ("/", "%") and ins.b == 0:
            return None
        if ins.op in ("<<", ">>") and not (isinstance(ins.a, int) and isinstance(ins.b, int)):
            return None
        return Instr("asignar", dst=ins.dst, a=OPS[ins.op](ins.a, ins.b))
    return None


def simplificar(ins, flotantes=()):
    """Identidades algebraicas: x+0, x-0, x*1, x/1, x<<0 -> x ;  x*0 -> 0 (enteros)."""
    if ins.tipo != "op":
        return None
    a, b, op = ins.a, ins.b, ins.op
    neutro = {"+": 0, "-": 0, "*": 1, "/": 1, "<<": 0, ">>": 0}
    if op in neutro and es_const(b) and b == neutro[op] and isinstance(a, str):
        return Instr("asignar", dst=ins.dst, a=a)
    if op in ("+", "*") and es_const(a) and a == neutro[op] and isinstance(b, str):
        return Instr("asignar", dst=ins.dst, a=b)
    if op == "*":
        for x, c in ((a, b), (b, a)):
            if isinstance(x, str) and x not in flotantes and type(c) is int and c == 0:
                return Instr("asignar", dst=ins.dst, a=0)
    return None


def plegado_constantes(codigo, flotantes=(), **_):
    codigo, cambios = copiar(codigo), []
    fl = variables_flotantes(codigo, flotantes)
    for i, ins in enumerate(codigo):
        if p := plegar(ins):
            cambios.append(f"{fmt(ins)}  ->  {fmt(p)}   (se calcula al compilar)")
            codigo[i] = p
        elif p := simplificar(ins, fl):
            cambios.append(f"{fmt(ins)}  ->  {fmt(p)}   (identidad algebraica)")
            codigo[i] = p
    return codigo, cambios


def propagacion_constantes(codigo, flotantes=(), **_):
    codigo, cambios = copiar(codigo), []
    fl = variables_flotantes(codigo, flotantes)
    g = GFC(codigo)
    _, _, IN, _ = defs_alcanzables(g)
    for b, idxs in enumerate(g.bloques):
        cur = set(IN[b])
        for i in idxs:
            ins, original = codigo[i], fmt(codigo[i])
            for campo in CAMPOS_USO.get(ins.tipo, ()):
                x = getattr(ins, campo)
                if not isinstance(x, str):
                    continue
                ds = [codigo[d] for d in cur if definida(codigo[d]) == x]
                if ds and all(d.tipo == "asignar" and es_const(d.a) for d in ds):
                    if len({(type(d.a), d.a) for d in ds}) == 1:
                        setattr(ins, campo, ds[0].a)
            if fmt(ins) != original:
                texto = f"{original}  ->  {fmt(ins)}"
                if (p := plegar(ins)) or (p := simplificar(ins, fl)):
                    codigo[i] = ins = p
                    texto += f"  ->  {fmt(ins)}"
                cambios.append(texto)
            if v := definida(ins):
                cur = {d for d in cur if definida(codigo[d]) != v} | {i}
    return codigo, cambios


def eliminacion_codigo_muerto(codigo, **_):
    codigo, cambios = copiar(codigo), []
    while True:
        antes = len(cambios)

        # a) condiciones que ya son constantes
        nuevo = []
        for ins in codigo:
            if ins.tipo == "si" and es_const(ins.a) and es_const(ins.b):
                if REL[ins.op](ins.a, ins.b):
                    n = Instr("ir", etiqueta=ins.etiqueta)
                    cambios.append(f"{fmt(ins)}  ->  {fmt(n)}   (la condición siempre se cumple)")
                    nuevo.append(n)
                else:
                    cambios.append(f"{fmt(ins)}  eliminado   (la condición nunca se cumple)")
                continue
            nuevo.append(ins)
        codigo = nuevo

        # b) bloques a los que nunca se llega
        g = GFC(codigo)
        alc = alcanzables(g)
        muertos = {i for b, idxs in enumerate(g.bloques) if b not in alc for i in idxs}
        for i in sorted(muertos):
            if codigo[i].tipo != "etiqueta":
                cambios.append(f"{fmt(codigo[i])}  eliminado   (nunca se ejecuta)")
        codigo = [ins for i, ins in enumerate(codigo) if i not in muertos]

        # c) goto que salta a la línea siguiente
        nuevo = []
        for i, ins in enumerate(codigo):
            if ins.tipo == "ir":
                j, siguientes = i + 1, set()
                while j < len(codigo) and codigo[j].tipo == "etiqueta":
                    siguientes.add(codigo[j].etiqueta)
                    j += 1
                if ins.etiqueta in siguientes:
                    cambios.append(f"{fmt(ins)}  eliminado   (salta a la línea siguiente)")
                    continue
            nuevo.append(ins)
        codigo = nuevo

        # d) etiquetas a las que nadie salta
        destinos = {ins.etiqueta for ins in codigo if ins.tipo in ("si", "ir")}
        nuevo = []
        for ins in codigo:
            if ins.tipo == "etiqueta" and ins.etiqueta not in destinos:
                cambios.append(f"{fmt(ins)}  eliminada   (nadie salta a ella)")
                continue
            nuevo.append(ins)
        codigo = nuevo

        # e) asignaciones que no influyen en el resultado ("marcar y barrer"):
        #    se marcan las instrucciones esenciales (return, print, escrituras,
        #    saltos) y, con definiciones alcanzables, todo lo que ellas necesitan.
        g = GFC(codigo)
        _, _, IN, _ = defs_alcanzables(g)
        rd = alcanzan_por_instr(g, IN)
        vivas, _, _ = vivas_por_instr(g)
        marcadas = {i for i, ins in enumerate(codigo) if not definida(ins)}
        pila = list(marcadas)
        while pila:
            i = pila.pop()
            for u in usadas(codigo[i]):
                for d in rd[i]:
                    if definida(codigo[d]) == u and d not in marcadas:
                        marcadas.add(d)
                        pila.append(d)
        nuevo = []
        for i, ins in enumerate(codigo):
            if i not in marcadas:
                v = definida(ins)
                motivo = "no se usa después" if v not in vivas[i] else "nunca influye en el resultado"
                cambios.append(f"{fmt(ins)}  eliminado   ('{v}' {motivo})")
                continue
            nuevo.append(ins)
        codigo = nuevo

        if len(cambios) == antes:
            return codigo, cambios


def _clave(ins):
    if ins.tipo == "op" and ins.op in PURAS:
        ops = (ins.a, ins.b)
        if ins.op in CONMUTATIVAS:
            ops = tuple(sorted(ops, key=lambda x: (type(x).__name__, str(x))))
        return ("op", ins.op, ops)
    if ins.tipo == "cargar":
        return ("cargar", ins.arr, (ins.a,))
    return None


def subexpresiones_comunes(codigo, **_):
    """Numeración de valores + propagación de copias. Es local a cada bloque,
    pero un bloque con UN solo predecesor hereda lo que se calculó en él
    (bloques básicos extendidos): lo que valía al salir de P vale al entrar a B."""
    codigo, cambios = copiar(codigo), []
    g = GFC(codigo)
    al_final = {}
    for b, idxs in enumerate(g.bloques):
        if len(g.pred[b]) == 1 and g.pred[b][0] in al_final:
            copias, exprs = (dict(t) for t in al_final[g.pred[b][0]])
        else:
            copias, exprs = {}, {}
        for i in idxs:
            ins, original = codigo[i], fmt(codigo[i])
            for campo in CAMPOS_USO.get(ins.tipo, ()):
                x = getattr(ins, campo)
                if isinstance(x, str) and x in copias:
                    setattr(ins, campo, copias[x])
            clave = _clave(ins)
            if clave in exprs and exprs[clave] != ins.dst:
                codigo[i] = ins = Instr("asignar", dst=ins.dst, a=exprs[clave])
            if fmt(ins) != original:
                cambios.append(f"{original}  ->  {fmt(ins)}")
            if v := definida(ins):
                copias = {k: w for k, w in copias.items() if v not in (k, w)}
                exprs = {k: h for k, h in exprs.items() if h != v and v not in k[2]}
                if ins.tipo == "asignar" and isinstance(ins.a, str) and ins.a != v:
                    copias[v] = ins.a
                elif ins.tipo in ("op", "cargar") and clave and v not in clave[2]:
                    exprs[clave] = v
            if ins.tipo == "guardar":
                exprs = {k: h for k, h in exprs.items() if not (k[0] == "cargar" and k[1] == ins.arr)}
        al_final[b] = (copias, exprs)
    if cambios:
        codigo, limpieza = eliminacion_codigo_muerto(codigo)
        cambios += ["(limpieza) " + c for c in limpieza]
    return codigo, cambios


def _invariantes(codigo, idx, en_ciclo, rd):
    inv, cambio = set(), True
    while cambio:
        cambio = False
        for i in idx:
            ins = codigo[i]
            if i in inv or not (ins.tipo == "asignar" or (ins.tipo == "op" and ins.op in PURAS)):
                continue
            ok = True
            for u in usadas(ins):
                ds = {d for d in rd[i] if definida(codigo[d]) == u}
                dentro = ds & en_ciclo
                if dentro and not (len(ds) == 1 and dentro <= inv):
                    ok = False
                    break
            if ok:
                inv.add(i)
                cambio = True
    return inv


def _mover_un_ciclo(codigo):
    g = GFC(codigo)
    dom = dominadores(g)
    _, _, IN, _ = defs_alcanzables(g)
    rd = alcanzan_por_instr(g, IN)
    _, vivas_entrada, _ = vivas_por_instr(g)
    for h, cuerpo in sorted(ciclos_naturales(g, dom).items()):
        fuera = [p for p in g.pred[h] if p not in cuerpo]
        if h == 0:
            if fuera:
                continue
        elif fuera != [h - 1] or codigo[g.bloques[h - 1][-1]].tipo in ("si", "ir", "retornar"):
            continue
        idx = sorted(i for b in cuerpo for i in g.bloques[b])
        en_ciclo = set(idx)
        inv = _invariantes(codigo, idx, en_ciclo, rd)
        salidas = [(b, s) for b in cuerpo for s in g.suc[b] if s not in cuerpo]
        mover = []
        for i in idx:
            if i not in inv:
                continue
            ins, x = codigo[i], codigo[i].dst
            if sum(definida(codigo[j]) == x for j in idx) != 1:
                continue
            if x in vivas_entrada[h]:
                continue
            bi = g.bloque_de[i]
            if any(bi not in dom[b] and x in vivas_entrada[s] for b, s in salidas):
                continue
            if any(d in en_ciclo and d not in mover
                   for u in usadas(ins) for d in rd[i] if definida(codigo[d]) == u):
                continue
            mover.append(i)
        if mover:
            ancla = codigo[g.bloques[h][0]]
            movidos = [codigo[i] for i in mover]
            nuevo = [ins for j, ins in enumerate(codigo) if j not in set(mover)]
            pos = next(k for k, ins in enumerate(nuevo) if ins is ancla)
            nuevo[pos:pos] = movidos
            nombre = ancla.etiqueta if ancla.tipo == "etiqueta" else f"B{h + 1}"
            textos = [f"{fmt(m)}  ->  se mueve antes del ciclo {nombre}   (no cambia en cada vuelta)"
                      for m in movidos]
            return nuevo, textos
    return None


def mover_invariantes(codigo, **_):
    codigo, cambios = copiar(codigo), []
    for _ in range(100):
        r = _mover_un_ciclo(codigo)
        if r is None:
            break
        codigo, textos = r
        cambios += textos
    return codigo, cambios


def variables_flotantes(codigo, iniciales=()):
    """Deduce qué variables pueden tener valor real (float)."""
    fl = set(iniciales)
    cambio = True
    while cambio:
        cambio = False
        for ins in codigo:
            v = definida(ins)
            if not v or v in fl:
                continue
            if ins.tipo == "asignar":
                f = isinstance(ins.a, float) or ins.a in fl
            elif ins.tipo == "op":
                f = any(isinstance(x, float) or x in fl for x in (ins.a, ins.b))
            else:
                f = ins.arr in fl
            if f:
                fl.add(v)
                cambio = True
    return fl


def reduccion_intensidad(codigo, flotantes=(), **_):
    """x * 2^k -> x << k   (solo con enteros)."""
    codigo, cambios = copiar(codigo), []
    fl = variables_flotantes(codigo, flotantes)
    for i, ins in enumerate(codigo):
        if ins.tipo == "op" and ins.op == "*":
            for x, c in ((ins.a, ins.b), (ins.b, ins.a)):
                if isinstance(x, str) and x not in fl and type(c) is int and c > 1 and c & (c - 1) == 0:
                    n = Instr("op", dst=ins.dst, a=x, op="<<", b=c.bit_length() - 1)
                    cambios.append(f"{fmt(ins)}  ->  {fmt(n)}   (multiplicar por {c} = correr {n.b} bits)")
                    codigo[i] = n
                    break
    return codigo, cambios


PASOS = [
    ("Plegado de constantes", plegado_constantes),
    ("Propagación de constantes", propagacion_constantes),
    ("Eliminación de código muerto", eliminacion_codigo_muerto),
    ("Subexpresiones comunes", subexpresiones_comunes),
    ("Código invariante en ciclos", mover_invariantes),
    ("Reducción de intensidad", reduccion_intensidad),
]


@dataclass
class Paso:
    ronda: int
    numero: int          # 1..6
    nombre: str
    cambios: list
    codigo: list         # código DESPUÉS del paso


def optimizar_registro(prog, activos=None, max_rondas=20):
    """Aplica los pasos activos en rondas hasta el punto fijo.
    Devuelve (programa optimizado, lista de Paso)."""
    activos = set(range(1, 7)) if activos is None else set(activos)
    codigo, registro = copiar(prog.codigo), []
    for ronda in range(1, max_rondas + 1):
        hubo = False
        for k, (nombre, paso) in enumerate(PASOS, 1):
            if k not in activos:
                continue
            codigo, cambios = paso(codigo, flotantes=prog.flotantes)
            hubo |= bool(cambios)
            registro.append(Paso(ronda, k, nombre, cambios, copiar(codigo)))
        if not hubo:
            break
    opt = replace(prog, nombre=prog.nombre + "_optimizado", codigo=codigo)
    return opt, registro


def optimizar(prog, detalle=True, activos=None):
    """Versión de consola: imprime los cambios y devuelve el programa optimizado."""
    opt, registro = optimizar_registro(prog, activos)
    if detalle:
        ronda_actual = 0
        for p in registro:
            if p.ronda != ronda_actual:
                ronda_actual = p.ronda
                if p.ronda > 1:
                    print(f"\n  -- Ronda {p.ronda} (se repiten los pasos hasta que nada cambie) --")
            if p.cambios or p.ronda == 1:
                print(f"\n  Paso {p.numero} · {p.nombre}")
                for c in p.cambios:
                    print(f"     • {c}")
                if not p.cambios:
                    print("     (sin cambios)")
        print("     Ningún paso cambió nada: se alcanzó el punto fijo.")
    return opt


# =============================================================================
# 5. Intérprete: ejecuta el código y cuenta operaciones
# =============================================================================

CATEGORIA = {"*": "multiplicaciones", "/": "divisiones", "%": "divisiones",
             "<<": "corrimientos", ">>": "corrimientos", "+": "sumas/restas", "-": "sumas/restas"}
ORDEN_CAT = ["multiplicaciones", "divisiones", "corrimientos", "sumas/restas",
             "comparaciones (if)", "lecturas de memoria", "escrituras de memoria",
             "copias", "saltos (goto)", "impresiones", "instrucciones totales"]


class ErrorEjecucion(Exception):
    pass


@dataclass
class Resultado:
    valor: object
    salida: list
    memoria: dict
    contador: Counter


def ejecutar(prog, args, arreglos, max_pasos=5_000_000):
    codigo = prog.codigo
    env = dict(args)
    mem = {k: list(v) for k, v in arreglos.items()}
    for nombre, tam in prog.locales.items():
        mem[nombre] = [0.0 if nombre in prog.flotantes else 0] * tam
    etiquetas = {ins.etiqueta: i for i, ins in enumerate(codigo) if ins.tipo == "etiqueta"}
    salida, c, pc = [], Counter(), 0

    def val(o):
        if isinstance(o, str):
            if o not in env:
                raise ErrorEjecucion(f"la variable '{o}' se usa sin valor")
            return env[o]
        return o

    def idx(arr, i):
        if arr not in mem:
            raise ErrorEjecucion(f"el arreglo '{arr}' no tiene datos")
        if not isinstance(i, int) or not 0 <= i < len(mem[arr]):
            raise ErrorEjecucion(f"índice {i} fuera de {arr}[0..{len(mem[arr]) - 1}]")
        return i

    try:
        while pc < len(codigo):
            ins, pc = codigo[pc], pc + 1
            t = ins.tipo
            if t == "etiqueta":
                continue
            c["instrucciones totales"] += 1
            if c["instrucciones totales"] > max_pasos:
                raise ErrorEjecucion(f"más de {max_pasos:,} instrucciones (¿ciclo infinito?)")
            if t == "asignar":
                env[ins.dst] = val(ins.a)
                c["copias"] += 1
            elif t == "op":
                x, y = val(ins.a), val(ins.b)
                if ins.op in ("/", "%") and y == 0:
                    raise ErrorEjecucion("división entre cero")
                env[ins.dst] = OPS[ins.op](x, y)
                c[CATEGORIA[ins.op]] += 1
            elif t == "cargar":
                env[ins.dst] = mem[ins.arr][idx(ins.arr, val(ins.a))]
                c["lecturas de memoria"] += 1
            elif t == "guardar":
                mem[ins.arr][idx(ins.arr, val(ins.a))] = val(ins.b)
                c["escrituras de memoria"] += 1
            elif t == "si":
                c["comparaciones (if)"] += 1
                if REL[ins.op](val(ins.a), val(ins.b)):
                    pc = etiquetas[ins.etiqueta]
            elif t == "ir":
                c["saltos (goto)"] += 1
                pc = etiquetas[ins.etiqueta]
            elif t == "imprimir":
                salida.append(ins.etiqueta if ins.a is None else val(ins.a))
                c["impresiones"] += 1
            elif t == "retornar":
                return Resultado(val(ins.a) if ins.a is not None else None, salida, mem, c)
    except (TypeError, OverflowError, ValueError) as e:
        raise ErrorEjecucion(str(e)) from e
    return Resultado(None, salida, mem, c)


# =============================================================================
# 6. Datos de entrada y verificación
# =============================================================================

def leer_entrada(texto):
    """Lee la línea '// @entrada: n=10, v=aleatorio(10)' de un archivo."""
    m = re.search(r"@entrada:?(.*)", texto)
    if not m:
        return {}
    valores = {}
    for parte in re.findall(r"(\w+)\s*=\s*(\[[^\]]*\]|\w+\([^)]*\)|[-\w.]+)", m[1]):
        valores[parte[0]] = parte[1]
    return valores


def valor_entrada(texto, param, semilla=1):
    """Convierte el texto de un campo de entrada en un número o una lista."""
    import random
    texto = texto.strip()
    if param.arreglo:
        if m := re.fullmatch(r"aleatorio\((\d+)\)", texto):
            rnd = random.Random(semilla)
            n = int(m[1])
            if param.flotante:
                return [round(rnd.uniform(-100, 100), 2) for _ in range(n)]
            return [rnd.randint(-100, 100) for _ in range(n)]
        if m := re.fullmatch(r"ceros\((\d+)\)", texto):
            return [0.0 if param.flotante else 0] * int(m[1])
        partes = [p for p in re.split(r"[,\s\[\]]+", texto) if p]
        try:
            return [float(p) if param.flotante else int(p) for p in partes]
        except ValueError:
            raise ValueError(f"'{param.nombre}': escribe números separados por comas, "
                             f"aleatorio(N) o ceros(N)") from None
    try:
        return float(texto) if param.flotante or "." in texto else int(texto)
    except ValueError:
        raise ValueError(f"'{param.nombre}' debe ser un número") from None


def _firma(prog, args, arr, max_pasos):
    try:
        r = ejecutar(prog, args, arr, max_pasos)
        return ("ok", r.valor, r.salida, r.memoria)
    except ErrorEjecucion as e:
        return ("error", type(e).__name__)


def verificar_aleatorio(p1, p2, pruebas=300, semilla=2026, max_pasos=200_000):
    """Ejecuta ambas versiones con entradas aleatorias.
    Devuelve (iguales, válidas, primer contraejemplo o None)."""
    import random
    rnd = random.Random(semilla)
    iguales = validas = 0
    for _ in range(pruebas):
        args, arr = {}, {}
        for p in p1.params:
            if p.arreglo:
                arr[p.nombre] = ([round(rnd.uniform(-50, 50), 2) for _ in range(800)] if p.flotante
                                 else [rnd.randint(-50, 50) for _ in range(800)])
            else:
                args[p.nombre] = round(rnd.uniform(-10, 10), 2) if p.flotante else rnd.randint(0, 12)
        f1, f2 = _firma(p1, args, arr, max_pasos), _firma(p2, args, arr, max_pasos)
        if f1[0] == "ok":
            validas += 1
        if f1 == f2:
            iguales += 1
        else:
            return iguales, validas, args
    return iguales, validas, None
