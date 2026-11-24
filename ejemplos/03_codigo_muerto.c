// TÉCNICA: Eliminación de código muerto
// Hay código que nunca se ejecuta (if (0), modo depuración apagado)
// y variables que se calculan pero no influyen en el resultado.
// @entrada: n=50, v=aleatorio(50)

int suma_positivos(int v[], int n) {
    int debug = 0;
    int contador = 0;       // se actualiza pero nadie lo usa
    int temporal = 99;      // nunca se usa
    int suma = 0;
    for (int i = 0; i < n; i++) {
        if (debug) {
            printf("revisando %d\n", i);
        }
        if (v[i] > 0) {
            suma = suma + v[i];
            contador = contador + 1;
        }
    }
    if (0) {
        printf("esto nunca se imprime\n");
    }
    return suma;
}
