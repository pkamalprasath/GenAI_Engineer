import os
import re
import matplotlib.pyplot as plt

# locate log file relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "log", "log.txt")

# regex patterns
step_re = re.compile(r"^(\d+)\s+(train|val|hella)\s+([\d\.]+)")
losses = {"train": [], "val": [], "hella": []}

# parse the log
with open(LOG_FILE, "r") as f:
    for line in f:
        m = step_re.match(line.strip())
        if not m:
            continue
        step = int(m.group(1))
        key = m.group(2)
        val = float(m.group(3))
        losses[key].append((step, val))

# sort each series by step
for k in losses:
    losses[k].sort(key=lambda x: x[0])

# extract arrays
steps_train, train_loss = zip(*losses["train"])
steps_val, val_loss     = zip(*losses["val"])
steps_hella, hella_acc  = zip(*losses["hella"])

# baselines
gpt2_val_loss = 3.1   # horizontal line at 3.1
gpt2_acc      = 0.29  # horizontal line at 0.29
gpt3_acc      = 0.33  # horizontal line at 0.33

# plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# --- left: Loss ---
ax1.plot(steps_train, train_loss, color="C0", label="Train Loss")
ax1.plot(steps_val,   val_loss,   color="C1", label="Val Loss")
ax1.axhline(gpt2_val_loss, color="C2", linestyle="--",
            label="OpenAI GPT-2 (124M) checkpoint val loss")
ax1.set_title("Loss")
ax1.set_xlabel("Steps")
ax1.set_ylabel("Loss")
ax1.legend(loc="upper right", frameon=True)
# force y-axis to start at 2:
ax1.set_ylim(bottom=2)

# --- right: HellaSwag Eval ---
ax2.plot(steps_hella, hella_acc, color="C0", label="Your Model Accuracy")
ax2.axhline(gpt2_acc, color="C1", linestyle="--",
            label="OpenAI GPT-2 (124M) checkpoint")
ax2.axhline(gpt3_acc, color="C2", linestyle="--",
            label="OpenAI GPT-3 (124M) checkpoint")
ax2.set_title("HellaSwag Eval")
ax2.set_xlabel("Steps")
ax2.set_ylabel("Accuracy")
ax2.legend(loc="lower right", frameon=True)

plt.tight_layout()
out_path = os.path.join(SCRIPT_DIR, "inference.png")
plt.savefig(out_path)
print(f"Saved plot to {out_path}")
