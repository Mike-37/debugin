// tests/fixtures/node_app.js
const agent = require('../../index'); // your package root
agent.start();

function add(x, y) {
  const z = x + y;            // <- T1 tracepoint
  return z;
}

function condExample(a, b) {
  const t = a * b;            // <- T2 with cond
  return t;
}

function burst(n) {
  let s = 0;
  for (let i=0; i<n; i++) {   // <- L1 logpoint: "i={{i}} s={{s}}"
    s += i;
  }
  return s;
}

function nested() {
  function inner(u) {         // <- T3
    return u * 2;
  }
  return inner(5);
}

module.exports = { add, condExample, burst, nested };