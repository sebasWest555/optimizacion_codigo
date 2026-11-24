// También se puede escribir directamente CÓDIGO DE TRES DIRECCIONES
// (como el Jimple de Soot). Variables sin definir = parámetros.
// @entrada: n=100
    s = 0
    i = 0
    paso = 1 + 1
L1:
    if i >= n goto L2
    t1 = paso * 4
    t2 = i * t1
    s = s + t2
    i = i + 1
    goto L1
L2:
    return s
