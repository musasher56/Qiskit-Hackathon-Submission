| Method | Assignment | Relief value | % of optimum |
|---|---|---|---|
| Greedy (ReliefLink today) | V1->R1, V2->R3, V4->R2 | 153.02 | 73.9% |
| Hungarian (1 task each) | V1->R5, V2->R1, V4->R2 | 172.37 | 83.3% |
| Exact (brute force) | V1->R5, V2->R1, V2->R3, V4->R2, V4->R4 | 207.00 | 100.0% |

| QAOA run | P(valid) | P(optimum) | P(>=90% of optimum) | Most frequent valid answer |
|---|---|---|---|---|
| cvar_p1 | 12.1% | 0.39% | 1.3% | 55.5% of optimum |
| cvar_p2 | 49.2% | 2.69% | 6.9% | 91.7% of optimum |
| cvar_p3 | 14.5% | 0.90% | 1.5% | 81.7% of optimum |
| cvar_p4 | 25.8% | 9.57% | 12.6% | 100.0% of optimum |
| cvar_p5 | 32.6% | 9.57% | 11.4% | 66.3% of optimum |
| standard_p1 | 68.7% | 0.51% | 3.8% | 43.0% of optimum |
| standard_p2 | 88.6% | 0.90% | 5.5% | 62.4% of optimum |
| standard_p3 | 92.3% | 1.44% | 7.5% | 62.4% of optimum |
| standard_p4 | 89.2% | 3.03% | 14.6% | 79.1% of optimum |
| standard_p5 | 91.2% | 6.18% | 23.7% | 100.0% of optimum |

Random guessing: P(optimum) = 1/2^10 = 0.0977%, P(valid) = 9.3%
