// PROGRAMA "REALISTA" CON TODO JUNTO
// Plegado, propagación, código muerto, subexpresiones comunes,
// código invariante y reducción de intensidad en un mismo programa.
// @entrada: n=500, precio=15, v=aleatorio(500)

int reporte_ventas(int v[], int n, int precio) {
    int modo_prueba = 0;
    int iva_por_mil = 16 * 10;
    int dias = 7;
    int semanas = 4;
    int periodo = dias * semanas;
    int ventas_contadas = 0;
    int total = 0;
    int mayor = 0;
    for (int i = 0; i < n; i++) {
        int bruto = v[i] * precio;
        int impuesto = v[i] * precio * iva_por_mil;
        int neto = bruto * 1000 + impuesto;
        int limite = precio * periodo;
        if (modo_prueba) {
            printf("venta %d: %d\n", i, neto);
        }
        if (neto > limite * 8) {
            total = total + neto;
            ventas_contadas = ventas_contadas + 1;
        }
        if (neto > mayor) mayor = neto;
    }
    return total + mayor * 2;
}
