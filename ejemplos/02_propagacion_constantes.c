// TÉCNICA: Propagación de constantes
// Variables que siempre valen lo mismo: se sustituyen por su valor
// y luego se pliegan las operaciones que quedan entre constantes.
// @entrada: x=7

int calcula(int x) {
    int base = 10;
    int factor = 3;
    int desplazamiento = base * factor + 5;
    int limite = desplazamiento * 2;
    int r = x + limite;
    return r;
}
