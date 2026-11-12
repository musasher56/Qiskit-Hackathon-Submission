# 3-minute video script: ReliefLink Surge Optimizer

Target length: **2:50** (the hard limit is 3:00). Roughly 400 spoken words.

## Before you record
1. Run `streamlit run app.py`. Leave depth at 4, click **Run QAOA** once and wait about a minute, so the result is cached and appears instantly on camera. Then untick and re-tick "Flood zone active", so that view is cached too.
2. Open these in tabs: `results/scenario.png`, `results/assignments.png`, `results/architecture.png`, `results/depth_sweep.png`.
3. Mac screen recording: QuickTime → File → New Screen Recording, with the microphone on. Or press Cmd+Shift+5.
4. Upload to Google Drive. Share → General access → **Anyone with the link**. Open the link in a private window to check it works.

---

## 0:00 – 0:20 · Hook
**Screen:** `scenario.png` (the town map with the flood).

> A flood hits a town. The nullah overflows, the GT Road bridge goes under, and eighteen road segments close. Six calls for help arrive at once and only five volunteers are on duty. Who goes where?

## 0:20 – 0:45 · The problem and who it serves
**Screen:** `assignments.png`, top-left panel (greedy).

> Our ReliefLink platform matches greedily, one request at a time. It sends Bilal, our only first-aider who can also swim, to the medical call because he's closest. Then a rescue that sat queued offline for forty minutes has no swimmer left. Greedy reaches 75% of the best possible outcome. Coordinators at a rescue service need a better answer in minutes, so we assign everyone jointly.

## 0:45 – 1:25 · Formulation and the quantum part
**Screen:** `architecture.png`, then point at box 5.

> Travel times follow open roads, using our spec's flood speeds. Each usable volunteer–request pair is a yes/no decision, which is one qubit. We prune pairs with no road, a missing skill, or outside a request's top three, so thirty pairs become fifteen qubits: 32,768 possible plans.
> The reward is the spec's priority times its match score. Penalties stop two volunteers leading one request. Our extension lets one volunteer serve two nearby requests in a single trip. The classical Hungarian algorithm can't express that pairwise term, but a QUBO can. We map it to an Ising Hamiltonian and run QAOA, hand-built in Qiskit, growing the circuit one layer at a time.

## 1:25 – 2:15 · Live demo
**Screen:** the Streamlit app.

> Here's the town: fifteen qubits, eighteen closed roads.
*(Click Run QAOA. It's cached, so it's instant.)*
> The circuit is trained and measured 4,096 times. The dark blue bar is the exact optimum, and it's the single most frequent outcome out of 32,768 possibilities.
*(Switch the map between Greedy, Hungarian, QAOA and Exact.)*
> Greedy: 75%. Hungarian: 87%; it fixes the swimmer problem but can't chain trips, so two requests go unserved. QAOA and the exact optimum serve all six: Ayesha does the medical call and then the shelter around the corner, and Sana does the rooftop rescue and then the food drop.
*(Untick "Flood zone active".)*
> Drain the flood and the bridge reopens, so the routes change.

## 2:15 – 2:45 · Results and honest limitations
**Screen:** `depth_sweep.png`, then the Limitations section of the README.

> Depth matters: shallow circuits don't help, but from depth four QAOA finds the optimum about 370 times more often than random guessing. To be honest, though: brute force is still faster at this size, we claim no speedup, success drops quickly as problems grow, and this all ran on a noiseless simulator. A real district would need far more qubits than today's hardware offers.

## 2:45 – 2:55 · Close
**Screen:** README top.

> ReliefLink Surge Optimizer: a real disaster-response decision on a flooded road network, mapped correctly onto a quantum circuit and measured honestly. Everything reproduces with one command. Thank you.

---

# Judge Q&A prep (likely questions, short answers)

**Why quantum, if Hungarian solves it?**
Hungarian only solves the one-task-per-volunteer version. Once a volunteer can serve two nearby requests in one trip, the objective has pairwise terms Hungarian can't represent. We include Hungarian precisely to show where classical methods are already enough.

**Is this faster than classical?**
No. At 15 qubits brute force takes well under a second, and training the circuit takes about a minute. We claim a correct mapping and an honest measurement, not a speedup.

**How do you know the mapping is correct?**
Two tests. The Ising energy equals the QUBO cost on all 32,768 bitstrings, and the diagonal of Qiskit's operator equals our cost table. Our spec's own worked examples (T1, T8, T20) also reproduce exactly.

**Why can QAOA output invalid answers?**
Constraints are soft penalties inside the energy, and QAOA samples a probability distribution. We check every sample against the rules, and only valid ones are used. The penalty sweep shows the trade-off: a bigger penalty gives fewer good answers.

**Why CVaR?**
We only act on the best samples, so we train the circuit to make good answers likely, not to make the average good. Standard QAOA's most frequent answer stayed near 60% of the optimum; CVaR's reached 100% at depth 4.

**Why grow the circuit layer by layer?**
With random starting angles, training got stuck at 15 qubits. Starting depth 1 from a grid search and stretching each optimum into the next depth (INTERP, Zhou et al. 2020) is a standard fix, and it's what made depth 4 work.

**Is the road map real?**
No. It's a synthetic street grid with a river and three bridges, so the routing logic is real but the town isn't. Real OpenStreetMap roads would plug into the same code.

**How was the penalty chosen?**
It's 1.5 × the largest reward. Anything above 1× guarantees the true minimum never breaks a rule (switching off a violating variable always lowers cost). In our sweep 1.5× gave the most valid answers; 1.1× gave a slightly higher optimum rate.

**Why report the most frequent answer, not the best sample?**
Because picking the best of 4,096 samples hides how concentrated the distribution is. P(optimum) and the most frequent answer show whether the circuit learned anything; random guessing hits the optimum 0.003% of the time.

**What about real hardware?**
Not tested. Noise would lower the success rates, and CVaR would have to be estimated from shots rather than read from the statevector.

**Where do the numbers come from?**
The formulas are from our ReliefLink Technical Context v2. Requests R1–R4 are its worked examples A–D and R5 is example F. The spec itself calls the weights unvalidated starting values.
