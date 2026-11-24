// TÉCNICA: Subexpresiones comunes
// (a + b) se calcula cuatro veces y (a + b) * c dos veces.
// @entrada: a=3, b=4, c=5

int formula(int a, int b, int c) {
    int x = (a + b) * c;
    int y = (a + b) * (a + b);
    int z = (a + b) * c + y;
    return x + y + z;
}
