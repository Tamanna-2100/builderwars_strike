.PHONY: demo reset test

demo:
	@trap "kill 0" SIGINT; (.venv/bin/uvicorn api:app --port 8000 &) && (cd ui && npm run dev)

reset:
	rm -rf runs/test* tests/test_security_*

test:
	.venv/bin/python -m pytest -v
