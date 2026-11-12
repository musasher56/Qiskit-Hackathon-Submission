import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
fig, ax = plt.subplots(figsize=(11, 7.4)); ax.axis("off")
INK="#1a1a1a"; GRAY="#f2f2f0"; EDGE="#555555"; Q="#dce8f8"; QE="#2a78d6"
def box(x,y,w,h,title,sub="",fc=GRAY,ec=EDGE):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.3,rounding_size=1.2",fc=fc,ec=ec,lw=1))
    ax.text(x+w/2,y+h/2+1.6,title,ha="center",va="center",fontsize=10.5,color=INK,weight="bold")
    ax.text(x+w/2,y+h/2-2.0,sub,ha="center",va="center",fontsize=8.6,color="#444")
def arrow(x1,y1,x2,y2,both=False,ls="-"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="<|-|>" if both else "-|>",mutation_scale=12,color=EDGE,lw=1.1,ls=ls))
def group(x,y,w,h,label):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.3,rounding_size=1.5",fc="none",ec="#9a9a9a",lw=1,ls="--"))
    ax.text(x+w-1.2,y+h-1.2,label,fontsize=9.5,color="#333",weight="bold",va="top",ha="right")
W=28
group(2,55,106,17,"ReliefLink platform (existing design, Technical Context v2)")
box(5,57,W-4,9,"Dispatch","spec §8 Stage 4")
box(31,57,W-4,9,"Intake","app, SMS, hubs")
box(57,57,W-4,9,"Priority + scoring","spec §7 and §8")
box(83,57,W-4,9,"Hazard zones","closed roads, bridges")
arrow(55.3,61.5,56.7,61.5)
group(2,2,106,45,"Surge Optimizer (this project)")
xs=[6,42,78]
box(xs[0],31,W,9,"1. Road routing","shortest open route, ETAs")
box(xs[1],31,W,9,"2. Pruning","skills, distance, top-3")
box(xs[2],31,W,9,"3. QUBO builder","rewards, one lead, chaining")
box(xs[2],17,W,9,"4. Ising mapping","x = (1 - z)/2, SparsePauliOp")
box(xs[1],17,W,9,"5. QAOA circuit (Qiskit)","H, RZ, RZZ, RX, p layers",fc=Q,ec=QE)
box(xs[0],17,W,9,"6. Measure + decode","4,096 shots, validity check")
box(xs[1],4,W,8,"Classical optimiser","COBYLA, standard or CVaR")
box(xs[0],4,W,8,"7. Evaluate","greedy, Hungarian, brute force")
arrow(34.3,35.5,41.7,35.5); arrow(70.3,35.5,77.7,35.5)
arrow(92,30.7,92,26.3)
arrow(77.7,21.5,70.3,21.5); arrow(41.7,21.5,34.3,21.5)
arrow(56,12.3,56,16.7,both=True)
arrow(20,16.7,20,12.3)
arrow(69,56.7,20,40.3); ax.text(44,50.5,"surge batch",fontsize=8.5,color="#444",ha="right")
arrow(95,56.7,56,40.3); ax.text(85,50.5,"hazards",fontsize=8.5,color="#444")
ax.plot([5.7,3.8,3.8,17],[21.5,21.5,51,51],color=EDGE,lw=1.1,ls="--")
arrow(17,51,17,56.7,ls="--")
ax.text(18.2,52.3,"chosen assignment",fontsize=8.5,color="#444")
ax.add_patch(FancyBboxPatch((60,-3.3),3,2.4,boxstyle="round,pad=0.1",fc=Q,ec=QE)); ax.text(64.5,-2.1,"Quantum step (simulated)",fontsize=8.5,va="center")
ax.add_patch(FancyBboxPatch((90,-3.3),3,2.4,boxstyle="round,pad=0.1",fc=GRAY,ec=EDGE)); ax.text(94.5,-2.1,"Classical",fontsize=8.5,va="center")
ax.set_xlim(0,110); ax.set_ylim(-5,73)
fig.savefig("results/architecture.png",dpi=200,bbox_inches="tight",facecolor="white")
