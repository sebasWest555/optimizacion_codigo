// TÉCNICA: Reducción de intensidad
// Multiplicar por potencias de 2 se cambia por corrimientos (<<),
// que son más baratos para el procesador.
// @entrada: n=100, v=aleatorio(100)

int escala(int v[], int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        int doble = v[i] * 2;
        int octuple = v[i] * 8;
        int por16 = 16 * v[i];
        total = total + doble + octuple + por16;
    }
    return total;
}
