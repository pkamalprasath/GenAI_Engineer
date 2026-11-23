# Fine-tuning with PEFT (LoRA, QLoRA) and Lamini

Course experiments on parameter-efficient fine-tuning using the Hugging Face `peft` library (not a from-scratch LoRA implementation).

## Files

| File | What it does |
|---|---|
| `01.LoRa_experiments.ipynb` | LoRA with `peft` (`LoraConfig`, `get_peft_model`) on `distilgpt2`, trained with the Hugging Face `Trainer` on a tiny instruction → Cypher dataset |
| `02.LoRA_colab_experiments.ipynb` | A Colab copy of the LoRA notebook with small changes |
| `03.QLoRa_experiments.ipynb` | QLoRA: `distilgpt2` loaded in 4-bit with `bitsandbytes`, plus a `peft` LoRA adapter, on the same instruction → Cypher data |
| `04.Lamini.py` | Managed fine-tuning through the Lamini API (`meta-llama/Meta-Llama-3-8B-Instruct`) on a small hard-coded Q&A set |

## Stack

`transformers`, `datasets`, `peft`, `accelerate`, `bitsandbytes`, `lamini`.

## Notes

- The training sets are tiny demonstration sets, so these notebooks show the mechanics, not model quality.
- Notebook outputs have been cleared.
- QLoRA needs a CUDA GPU (for example a Colab T4).

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
