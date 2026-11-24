// EJEMPLO 1 DE LA EXPOSICIÓN (diapositiva 8)
// y = a * b y k = 2 * 3.14 no cambian dentro del ciclo.
// @entrada: n=100, a=3, b=4, v=ceros(100)

void ejemplo(float v[], int n, int a, int b) {
    int y;
    float k;
    for (int i = 0; i < n; i++) {
        y = a * b;
        k = 2 * 3.14;
        v[i] = y + k * i;
    }
}
