# C++ / Python engine baseline

This is a microbenchmark of the engine boundary, not a training or MCTS result.
Both runs used the same base-Hive rules and a deterministic 28-ply position made
by selecting the first sorted legal action at every ply.

Environment: Apple M3, arm64, macOS 26.5.2; C++ Release; Python 3.12.6.
Each operation ran 5,000 times in one process.

| Operation | Native C++ | Python + pybind11 |
|---|---:|---:|
| Generate legal actions | 161.6 µs/call | 184.8 µs/call |
| Clone, generate actions, apply one | 335.2 µs/call | 368.5 µs/call |
| Build history-aware state key | 22.6 µs/call | — |

The Python legal-action call also converts each action to a Python dictionary;
the observed difference is about 23 µs for this position. Both runners emit the
same state-key digest (`12e6ab23c12e4840`) to check they reached the same
position. The clone/apply figure includes move generation in both languages. It is useful as a reproducible
starting point, but it does not measure neural inference, MCTS tree management,
self-play throughput, or the final encoder. Profile those after the policy map
and network contract are implemented.

Reproduce from the project root:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DHIVE_BUILD_GUI=OFF
cmake --build build --target hive_bench
./build/hive_bench 5000

cd bindings/python
python -m pip install -e .
python ../../benchmarks/python_bridge_benchmark.py --iterations 5000
```
