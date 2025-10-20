# tests/fixtures/py_app.py
import time
from tracepointdebug import start as agent_start

agent_start()  # starts broker/engine; pytrace forced in true FT

def add(x, y):
    z = x + y           # <- T1 tracepoint here
    return z

def cond_example(a, b):
    t = (a * b)         # <- T2 tracepoint here
    return t

def burst(n):
    s = 0
    for i in range(n):  # <- L1 logpoint here
        s += i
    return s

def nested():
    def inner(u):       # <- T3 tracepoint here (nested)
        return u * 2
    return inner(5)

if __name__ == "__main__":
    add(2, 3)
    cond_example(2, 5)
    burst(2000)
    nested()