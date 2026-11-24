// TÉCNICA: Código invariante en ciclos
// area y borde no dependen de i, pero se recalculan en cada vuelta.
// @entrada: n=100, ancho=8, alto=5, v=ceros(100)

void llenar(int v[], int n, int ancho, int alto) {
    for (int i = 0; i < n; i++) {
        int area = ancho * alto;
        int borde = 2 * ancho + 2 * alto;
        v[i] = area * i + borde;
    }
}
