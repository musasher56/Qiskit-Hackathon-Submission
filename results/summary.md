| Method | Assignment | Relief value | % of optimum |
|---|---|---|---|
| Greedy (ReliefLink today) | V1->R1, V2->R3, V4->R2, V5->R6 | 164.34 | 75.3% |
| Hungarian (1 task each) | V1->R5, V2->R1, V4->R2, V5->R3 | 190.65 | 87.3% |
| Exact (brute force) | V1->R5, V2->R1, V2->R3, V4->R2, V4->R4, V5->R6 | 218.32 | 100.0% |

| QAOA run | P(valid) | P(optimum) | P(>=90% of optimum) | Most frequent valid answer |
|---|---|---|---|---|
| cvar_p1 | 48.2% | 0.02% | 0.7% | 31.7% of optimum |
| cvar_p2 | 71.9% | 0.02% | 0.9% | 20.4% of optimum |
| cvar_p3 | 79.9% | 0.02% | 1.2% | 59.2% of optimum |
| cvar_p4 | 62.9% | 1.32% | 7.6% | 86.8% of optimum |
| cvar_p5 | 60.3% | 1.76% | 13.2% | 95.2% of optimum |
| standard_p1 | 57.8% | 0.02% | 0.3% | 26.4% of optimum |
| standard_p2 | 82.0% | 0.05% | 0.8% | 59.2% of optimum |
| standard_p3 | 88.7% | 0.10% | 1.0% | 59.2% of optimum |
| standard_p4 | 87.4% | 0.39% | 4.4% | 78.9% of optimum |
| standard_p5 | 89.3% | 0.83% | 6.8% | 59.2% of optimum |

Random guessing: P(optimum) = 1/2^15 = 0.0031%, P(valid) = 0.8%
