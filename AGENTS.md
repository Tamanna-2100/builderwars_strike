# verity
Pipeline: scan -> verify reproduction test -> patch -> replay SAME test -> regression test -> report.
Rules: No proof, no alert. No failed exploit, no merge. LLM outputs JSON only; Python harness executes. Never run LLM-generated shell commands. Synthetic data only; sandbox localhost only.
Stack: Python 3.12, FastAPI, Flask+SQLite in /target, React+Tailwind in /ui, boto3 Bedrock Converse, Docker, pytest. Region/profile/models/bucket come from .env only.
Style: minimal code, no comments, reply with changed files only.

Hypothesis: {"id","vuln_type","file","route","line","reason"}
TestSpec: {"id","title","vuln_type","file","steps":[{"as":"alice|bob|anon","method","path","body?"}],"expected_outcome":{"status":int,"body_contains":str}}
state.json (/runs/{id}/state.json): {"run_id","status","stats":{"hypotheses","verified","fixed","discarded"},"steps":[{"name","status":"pending|running|done|failed","detail"}],"findings":[{"id","title","verdict":"confirmed|discarded","evidence":{"request","response"},"patch":{"file","diff","summary"},"replay":"blocked|still_vulnerable","test":str}]}
Finding explanation: {"severity":"high|medium|low","explain":{"story":str,"why_it_matters":str,"mistake_pattern":str,"prevention_rule":str,"ai_prompt":str}}

