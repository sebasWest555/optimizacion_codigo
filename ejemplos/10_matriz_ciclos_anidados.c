// CICLOS ANIDADOS
// columnas * 4 no depende ni de i ni de j: sale de los DOS ciclos.
// i * columnas no depende de j: sale del ciclo interno.
// @entrada: filas=20, columnas=30, m=aleatorio(600)

int suma_matriz(int m[], int filas, int columnas) {
    int suma = 0;
    for (int i = 0; i < filas; i++) {
        for (int j = 0; j < columnas; j++) {
            int pos = i * columnas + j;
            int peso = columnas * 4;
            suma = suma + m[pos] * peso;
        }
    }
    return suma;
}
