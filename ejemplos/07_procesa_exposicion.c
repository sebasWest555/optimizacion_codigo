// EJEMPLO 2 DE LA EXPOSICIÓN (diapositivas 9-11)
// Tiene oportunidades para las seis técnicas.
// @entrada: n=1000, k=7, v=aleatorio(1000)

int procesa(int v[], int n, int k) {
    int debug = 0;
    int escala = 4 * 8;
    int suma = 0;
    for (int i = 0; i < n; i++) {
        int lim = k * escala;
        if (debug) printf("%d\n", i);
        int a = v[i] * 2 + lim;
        int b = v[i] * 2 + lim;
        suma = suma + a + b;
    }
    return suma;
}
