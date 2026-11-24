// EJEMPLO DE DEFINICIONES ALCANZABLES (diapositiva 17)
// A "z = x + y" llegan d2 (y = x + 2) y d3 (x = 10); d1 queda anulada.
// Propagando constantes: z = 10 + 7 = 17.

int main() {
    int x = 5;
    int y = x + 2;
    x = 10;
    int z = x + y;
    return z;
}
