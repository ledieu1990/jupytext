/ ---
/ jupyter:
/   kernelspec:
/     display_name: Q 3.5
/     language: q
/     name: qpk
/ ---

plt: .p.import`matplotlib.pyplot

/ +
filter: {
    t: ([] x: `float $ x; xh: `float $ x; p: (count x) # R: var x);
    (first t), iterate[R; R]\[first t; 1 _ t] 
    }

iterate: {[Q; R; x; y]
    x[`p]+: Q;
    k: x[`p] % R + x[`p];
    `x`xh`p ! (y[`x]; x[`xh] + k * y[`x] - x[`xh]; (1 - k) * x[`p])
    }
/ -

price: 100 + sums 0.5 - (n:50)?1.

output:filter price

plt[`:plot][til n; output`x; `label pykw "price"];
plt[`:plot][til n; output`xh;`label pykw "forecast"];
plt[`:legend][];
plt[`:show][];


