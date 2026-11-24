# -*- coding: utf-8 -*-
"""
Mini-compilador: traduce un subconjunto de C a código de tres direcciones.

Soporta: una función (o sentencias sueltas), int/float/double, arreglos,
asignaciones (=, +=, -=, *=, /=, %=, <<=, >>=, ++, --), expresiones
aritméticas (+ - * / % << >>), condiciones con < <= > >= == != && || !,
if/else, while, do-while, for, break, continue, return y printf.

La traducción es dirigida por la sintaxis (descenso recursivo) y genera el
código SIN optimizar, como lo haría la fase de código intermedio.
"""

import re

from optimizador import INVERSA, Instr, Param, Programa

TIPOS = {"int", "float", "double", "long", "short", "char", "void", "unsigned"}
FLOTANTES = {"float", "double"}

_TOKEN = re.compile(r"""
    (?P<espacio>[ \t\r]+) | (?P<linea>\n) |
    (?P<comentario>//[^\n]*|/\*.*?\*/) |
    (?P<directiva>\#[^\n]*) |
    (?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?) |
    (?P<cadena>"(?:\\.|[^"\\])*") |
    (?P<id>[A-Za-z_]\w*) |
    (?P<op><<=|>>=|\+\+|--|\+=|-=|\*=|/=|%=|<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%<>=!(){}\[\];,&|^~?:.])
""", re.S | re.X)


class ErrorC(Exception):
    pass


def tokenizar(texto):
    toks, linea, pos = [], 1, 0
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if not m:
            raise ErrorC(f"Línea {linea}: carácter inesperado {texto[pos]!r}")
        tipo, valor = m.lastgroup, m.group()
        if tipo == "num":
            v = float(valor) if any(ch in valor for ch in ".eE") else int(valor)
            toks.append(("num", v, linea))
        elif tipo in ("id", "op", "cadena"):
            toks.append((tipo, valor, linea))
        linea += valor.count("\n")
        pos = m.end()
    toks.append(("fin", None, linea))
    return toks


class Traductor:
    def __init__(self, texto):
        self.toks = tokenizar(texto)
        self.p = 0
        self.codigo = []
        self.reservados = {v for t, v, _ in self.toks if t == "id"}
        self.nt = self.nl = 0
        self.flotantes = set()
        self.locales = {}
        self.ciclos = []          # pila de {"romper": L, "seguir": L | None}

    # ---- utilidades -------------------------------------------------------
    @property
    def actual(self):
        return self.toks[self.p]

    def ver(self, *valores):
        t, v, _ = self.actual
        return t in ("op", "id") and v in valores

    def tomar(self, valor=None, tipo=None):
        t, v, ln = self.actual
        if (valor is not None and v != valor) or (tipo is not None and t != tipo):
            esperado = valor or tipo
            encontrado = "fin del archivo" if t == "fin" else repr(v)
            raise ErrorC(f"Línea {ln}: se esperaba '{esperado}' y se encontró {encontrado}")
        self.p += 1
        return v

    def error(self, msg):
        raise ErrorC(f"Línea {self.actual[2]}: {msg}")

    def temporal(self):
        while True:
            self.nt += 1
            nombre = f"t{self.nt}"
            if nombre not in self.reservados:
                return nombre

    def nueva_etiqueta(self):
        self.nl += 1
        return f"L{self.nl}"

    def emitir(self, **kw):
        self.codigo.append(Instr(**kw))

    # ---- programa ---------------------------------------------------------
    def programa(self):
        params, nombre = [], "programa"
        es_funcion = (self.actual[1] in TIPOS and self.toks[self.p + 1][0] == "id"
                      and self.toks[self.p + 2][1] == "(")
        if es_funcion:
            while self.actual[1] in TIPOS:
                self.tomar()
            nombre = self.tomar(tipo="id")
            self.tomar("(")
            if self.ver("void") and self.toks[self.p + 1][1] == ")":
                self.tomar()
            while not self.ver(")"):
                tipos = []
                while self.actual[1] in TIPOS or self.ver("const"):
                    tipos.append(self.tomar())
                if not tipos:
                    self.error("se esperaba el tipo del parámetro")
                if self.ver("*"):
                    self.tomar()
                    arreglo = True
                else:
                    arreglo = False
                pn = self.tomar(tipo="id")
                if self.ver("["):
                    self.tomar("[")
                    if self.actual[0] == "num":
                        self.tomar()
                    self.tomar("]")
                    arreglo = True
                flot = bool(FLOTANTES & set(tipos))
                params.append(Param(pn, arreglo, flot))
                if flot:
                    self.flotantes.add(pn)
                if not self.ver(")"):
                    self.tomar(",")
            self.tomar(")")
            self.tomar("{")
            while not self.ver("}"):
                self.sentencia()
            self.tomar("}")
            if self.actual[0] != "fin":
                self.error("solo se admite una función por archivo")
        else:
            while self.actual[0] != "fin":
                self.sentencia()
        if not self.codigo or self.codigo[-1].tipo != "retornar":
            self.emitir(tipo="retornar")
        return Programa(nombre, self.codigo, params, set(self.flotantes), dict(self.locales))

    # ---- sentencias -------------------------------------------------------
    def sentencia(self):
        t, v, _ = self.actual
        if v == "{" and t == "op":
            self.tomar("{")
            while not self.ver("}"):
                self.sentencia()
            self.tomar("}")
        elif t == "op" and v == ";":
            self.tomar()
        elif t == "id" and (v in TIPOS or v == "const"):
            self.declaracion()
            self.tomar(";")
        elif v == "if" and t == "id":
            self.sent_if()
        elif v == "while" and t == "id":
            self.sent_while()
        elif v == "do" and t == "id":
            self.sent_do()
        elif v == "for" and t == "id":
            self.sent_for()
        elif v == "return" and t == "id":
            self.tomar()
            if self.ver(";"):
                self.emitir(tipo="retornar")
            else:
                self.emitir(tipo="retornar", a=self.valor(self.expr()))
            self.tomar(";")
        elif v in ("break", "continue") and t == "id":
            self.tomar()
            if not self.ciclos:
                self.error(f"'{v}' fuera de un ciclo")
            ciclo = self.ciclos[-1]
            if v == "break":
                destino = ciclo["romper"]
            else:
                if ciclo["seguir"] is None:
                    ciclo["seguir"] = self.nueva_etiqueta()
                destino = ciclo["seguir"]
            self.emitir(tipo="ir", etiqueta=destino)
            self.tomar(";")
        elif v == "printf" and t == "id":
            self.sent_printf()
            self.tomar(";")
        else:
            self.asignacion()
            self.tomar(";")

    def declaracion(self):
        tipos = []
        while self.actual[1] in TIPOS or self.ver("const"):
            tipos.append(self.tomar())
        flot = bool(FLOTANTES & set(tipos))
        while True:
            nombre = self.tomar(tipo="id")
            if flot:
                self.flotantes.add(nombre)
            if self.ver("["):
                self.tomar("[")
                tam = self.tomar(tipo="num")
                self.tomar("]")
                self.locales[nombre] = int(tam)
            elif self.ver("="):
                self.tomar("=")
                self.generar_en(self.expr(), nombre)
            if not self.ver(","):
                break
            self.tomar(",")

    def asignacion(self):
        t, v, ln = self.actual
        if t == "op" and v in ("++", "--"):
            self.tomar()
            nombre = self.tomar(tipo="id")
            self.emitir(tipo="op", dst=nombre, a=nombre, op=v[0], b=1)
            return
        if t != "id":
            self.error(f"sentencia no válida: {v!r}")
        nombre = self.tomar(tipo="id")
        if self.ver("("):
            self.error(f"las llamadas a funciones ('{nombre}(...)') no están soportadas")
        indice = None
        if self.ver("["):
            self.tomar("[")
            indice = self.expr()
            self.tomar("]")
        op = self.tomar(tipo="op")
        if op in ("++", "--"):
            rhs = ("bin", op[0], self._lvalor(nombre, indice), ("num", 1))
        elif op == "=":
            rhs = self.expr()
        elif op in ("+=", "-=", "*=", "/=", "%=", "<<=", ">>="):
            rhs = ("bin", op[:-1], self._lvalor(nombre, indice), self.expr())
        else:
            raise ErrorC(f"Línea {ln}: se esperaba '=' después de '{nombre}'")
        if indice is None:
            self.generar_en(rhs, nombre)
        else:
            i = self.valor(indice)
            self.emitir(tipo="guardar", arr=nombre, a=i, b=self.valor(rhs))

    @staticmethod
    def _lvalor(nombre, indice):
        return ("var", nombre) if indice is None else ("idx", nombre, indice)

    def sent_if(self):
        self.tomar("if")
        self.tomar("(")
        cond = self.condicion()
        self.tomar(")")
        l_falso = self.nueva_etiqueta()
        self.salto_si_falso(cond, l_falso)
        self.sentencia()
        if self.ver("else"):
            self.tomar("else")
            l_fin = self.nueva_etiqueta()
            self.emitir(tipo="ir", etiqueta=l_fin)
            self.emitir(tipo="etiqueta", etiqueta=l_falso)
            self.sentencia()
            self.emitir(tipo="etiqueta", etiqueta=l_fin)
        else:
            self.emitir(tipo="etiqueta", etiqueta=l_falso)

    def _cuerpo_ciclo(self, l_fin, l_seguir=None):
        ciclo = {"romper": l_fin, "seguir": l_seguir}
        self.ciclos.append(ciclo)
        self.sentencia()
        self.ciclos.pop()
        return ciclo

    def sent_while(self):
        self.tomar("while")
        self.tomar("(")
        cond = self.condicion()
        self.tomar(")")
        l_ini, l_fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.emitir(tipo="etiqueta", etiqueta=l_ini)
        self.salto_si_falso(cond, l_fin)
        self._cuerpo_ciclo(l_fin, l_ini)
        self.emitir(tipo="ir", etiqueta=l_ini)
        self.emitir(tipo="etiqueta", etiqueta=l_fin)

    def sent_do(self):
        self.tomar("do")
        l_ini, l_fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.emitir(tipo="etiqueta", etiqueta=l_ini)
        ciclo = self._cuerpo_ciclo(l_fin)
        self.tomar("while")
        self.tomar("(")
        cond = self.condicion()
        self.tomar(")")
        self.tomar(";")
        if ciclo["seguir"]:
            self.emitir(tipo="etiqueta", etiqueta=ciclo["seguir"])
        self.salto_si_verdadero(cond, l_ini)
        self.emitir(tipo="etiqueta", etiqueta=l_fin)

    def sent_for(self):
        self.tomar("for")
        self.tomar("(")
        if not self.ver(";"):
            if self.actual[1] in TIPOS:
                self.declaracion()
            else:
                self.asignacion()
        self.tomar(";")
        cond = None if self.ver(";") else self.condicion()
        self.tomar(";")
        # el incremento se traduce después del cuerpo: guardamos sus tokens
        inicio = self.p
        nivel = 0
        while not (self.ver(")") and nivel == 0):
            if self.ver("("):
                nivel += 1
            elif self.ver(")"):
                nivel -= 1
            if self.actual[0] == "fin":
                self.error("falta ')' en el for")
            self.p += 1
        fin_incr = self.p
        self.tomar(")")
        l_ini, l_fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.emitir(tipo="etiqueta", etiqueta=l_ini)
        if cond is not None:
            self.salto_si_falso(cond, l_fin)
        ciclo = self._cuerpo_ciclo(l_fin)
        if ciclo["seguir"]:
            self.emitir(tipo="etiqueta", etiqueta=ciclo["seguir"])
        if fin_incr > inicio:
            guardado = self.p
            self.p = inicio
            while self.p < fin_incr:
                self.asignacion()
                if self.p < fin_incr:
                    self.tomar(",")
            self.p = guardado
        self.emitir(tipo="ir", etiqueta=l_ini)
        self.emitir(tipo="etiqueta", etiqueta=l_fin)

    def sent_printf(self):
        self.tomar("printf")
        self.tomar("(")
        texto = self.tomar(tipo="cadena")[1:-1]
        args = []
        while self.ver(","):
            self.tomar(",")
            args.append(self.expr())
        self.tomar(")")
        if not args:
            self.emitir(tipo="imprimir", etiqueta=texto)
        for a in args:
            self.emitir(tipo="imprimir", a=self.valor(a))

    # ---- expresiones (árbol) ----------------------------------------------
    def condicion(self):
        izq = self.cond_and()
        while self.ver("||"):
            self.tomar()
            izq = ("o", izq, self.cond_and())
        return izq

    def cond_and(self):
        izq = self.cond_not()
        while self.ver("&&"):
            self.tomar()
            izq = ("y", izq, self.cond_not())
        return izq

    def cond_not(self):
        if self.ver("!"):
            self.tomar()
            return ("no", self.cond_not())
        izq = self.expr()
        if self.actual[0] == "op" and self.actual[1] in INVERSA:
            op = self.tomar()
            return ("rel", op, izq, self.expr())
        return izq

    def expr(self):
        izq = self.suma()
        while self.ver("<<", ">>"):
            op = self.tomar()
            izq = ("bin", op, izq, self.suma())
        return izq

    def suma(self):
        izq = self.termino()
        while self.ver("+", "-"):
            op = self.tomar()
            izq = ("bin", op, izq, self.termino())
        return izq

    def termino(self):
        izq = self.unario()
        while self.ver("*", "/", "%"):
            op = self.tomar()
            izq = ("bin", op, izq, self.unario())
        return izq

    def unario(self):
        if self.ver("-"):
            self.tomar()
            e = self.unario()
            return ("num", -e[1]) if e[0] == "num" else ("bin", "-", ("num", 0), e)
        if self.ver("+"):
            self.tomar()
            return self.unario()
        return self.primario()

    def primario(self):
        t, v, _ = self.actual
        if t == "num":
            self.tomar()
            return ("num", v)
        if t == "op" and v == "(":
            self.tomar("(")
            if self.actual[1] in TIPOS:          # conversión: (int) x, (float) x
                self.error("las conversiones de tipo (cast) no están soportadas")
            e = self.condicion()
            self.tomar(")")
            return e
        if t == "id":
            nombre = self.tomar()
            if self.ver("("):
                self.error(f"las llamadas a funciones ('{nombre}(...)') no están soportadas")
            if self.ver("["):
                self.tomar("[")
                i = self.expr()
                self.tomar("]")
                return ("idx", nombre, i)
            if self.ver("++", "--"):
                self.error("usa i++ como sentencia aparte, no dentro de una expresión")
            return ("var", nombre)
        self.error(f"expresión no válida cerca de {v!r}")

    # ---- generación de código ---------------------------------------------
    def valor(self, nodo):
        """Genera el código del nodo y devuelve el operando con su valor."""
        k = nodo[0]
        if k == "num":
            return nodo[1]
        if k == "var":
            return nodo[1]
        if k in ("bin", "idx"):
            t = self.temporal()
            self.generar_en(nodo, t)
            return t
        self.error("una comparación solo puede usarse dentro de if/while/for")

    def generar_en(self, nodo, destino):
        k = nodo[0]
        if k == "bin":
            a = self.valor(nodo[2])
            b = self.valor(nodo[3])
            self.emitir(tipo="op", dst=destino, a=a, op=nodo[1], b=b)
        elif k == "idx":
            i = self.valor(nodo[2])
            self.emitir(tipo="cargar", dst=destino, arr=nodo[1], a=i)
        else:
            self.emitir(tipo="asignar", dst=destino, a=self.valor(nodo))

    def salto_si_falso(self, c, destino):
        k = c[0]
        if k == "rel":
            a, b = self.valor(c[2]), self.valor(c[3])
            self.emitir(tipo="si", a=a, op=INVERSA[c[1]], b=b, etiqueta=destino)
        elif k == "y":
            self.salto_si_falso(c[1], destino)
            self.salto_si_falso(c[2], destino)
        elif k == "o":
            l_ok = self.nueva_etiqueta()
            self.salto_si_verdadero(c[1], l_ok)
            self.salto_si_falso(c[2], destino)
            self.emitir(tipo="etiqueta", etiqueta=l_ok)
        elif k == "no":
            self.salto_si_verdadero(c[1], destino)
        else:
            self.emitir(tipo="si", a=self.valor(c), op="==", b=0, etiqueta=destino)

    def salto_si_verdadero(self, c, destino):
        k = c[0]
        if k == "rel":
            a, b = self.valor(c[2]), self.valor(c[3])
            self.emitir(tipo="si", a=a, op=c[1], b=b, etiqueta=destino)
        elif k == "y":
            l_no = self.nueva_etiqueta()
            self.salto_si_falso(c[1], l_no)
            self.salto_si_verdadero(c[2], destino)
            self.emitir(tipo="etiqueta", etiqueta=l_no)
        elif k == "o":
            self.salto_si_verdadero(c[1], destino)
            self.salto_si_verdadero(c[2], destino)
        elif k == "no":
            self.salto_si_falso(c[1], destino)
        else:
            self.emitir(tipo="si", a=self.valor(c), op="!=", b=0, etiqueta=destino)


def compilar_c(texto):
    """Código C -> Programa (código de tres direcciones sin optimizar)."""
    return Traductor(texto).programa()
