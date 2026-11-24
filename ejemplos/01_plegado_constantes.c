// TÉCNICA: Plegado de constantes
// Operaciones entre constantes que el programa recalcula en cada
// ejecución, aunque su resultado siempre es el mismo.
// @entrada: dias=30

int segundos_del_mes(int dias) {
    int segundos_por_dia = 60 * 60 * 24;
    int minutos_por_semana = 7 * 24 * 60;
    int total = dias * segundos_por_dia + minutos_por_semana * 0;
    return total;
}
