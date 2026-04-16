# 03. AI Guardrails & Safety

Practical implementation of AI safety techniques — detecting and preventing prompt injection, hallucination, sensitive data leakage, and adversarial attacks.

## Modules

| Module | What It Covers |
|---|---|
| [01. Guardrails AI](./01.Guardrails/) | Input/output validation with the Guardrails AI framework |
| [02. NeMo Guardrails](./02.NemoGuardRails/) | NVIDIA NeMo Guardrails — colang flows for topic control and safety rails |
| [03. Evaluators](./03.Evaluators/) | Automated evaluation of LLM outputs for safety and quality |
| [04. Prompt Injection](./04.Prompt_Injection/) | Detection and prevention of prompt injection attacks |
| [05. Sensitive Information](./05.Sensitive_Information/) | PII detection, data masking, and sensitive data filtering |
| [06. Hallucination](./06.Hallucination/) | Hallucination detection using fact-checking and consistency checks |
| [07. Garak](./07.Garak/) | Red-teaming LLMs with the Garak adversarial testing framework |
| [08. Security Testing](./08.Security_Testing/) | End-to-end AI security assessment with CrewAI agents |

## Why This Matters

Every production AI system needs safety layers. This module covers the full spectrum:
- **Input validation** — block malicious or off-topic inputs
- **Output validation** — catch hallucinations and PII before responses reach users
- **Red-teaming** — systematically probe for vulnerabilities before deployment

## Skills Demonstrated

- Guardrails AI validator pipelines
- NeMo Guardrails colang flow authoring
- Prompt injection taxonomy and mitigations
- RAGAS-based hallucination scoring
- Garak automated red-teaming
- CrewAI security testing agents
