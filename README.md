# Sapiens4 Sales Lead Benchmark

`SALEAD-001` is a controlled benchmark for evaluating whether an agent system
can qualify an inbound AI-consulting lead, coordinate delegated research,
update business state, recover from a transient CRM failure, and create the
correct follow-up.

The current MVP contains the benchmark contract, resettable mock environment,
auditable tools, deterministic evaluator, tests, and a scripted reference run.
The reference runner validates the benchmark infrastructure; it is not a
Sapiens4 result. A live Sapiens4 adapter is the next integration step.

## Validate the benchmark contract

```bash
python3 -m benchmark.validate
```

Expected output:

```text
SALEAD-001 configuration is valid.
Initial fixtures are valid.
Golden state is valid.
Foundation validation passed.
```

## Run the environment and evaluator demo

```bash
python3 -m benchmark.demo
```

Expected output:

```text
SALEAD-001 reference environment run completed.
Deterministic score: 9.00/9.00
LLM-as-a-Judge: pending (1.00 point)
Current verified score: 9.00/10.00
Report: runs/reference/evaluation-report.json
Visual report: runs/reference/evaluation-report.html
LLM judge request: runs/reference/llm-judge-request.json
```

The final one-point communication score remains pending until a real LLM judge
is configured. To demonstrate score aggregation with an externally reviewed
judge score:

```bash
python3 -m benchmark.demo --judge-score 0.9
```

## Run tests

```bash
python3 -m unittest discover -v
```

## Structure

```text
benchmark/environment.py    Resettable mock applications and audit trace
benchmark/evaluator.py      Deterministic 9-point evaluator
benchmark/judge.py          Bounded one-point LLM-judge request/validation
benchmark/demo.py           Scripted reference run (not a Sapiens4 result)
benchmark/validate.py       Contract and fixture validation
challenge/salead-001.json   Agent-visible challenge definition
fixtures/initial_state.json Resettable environment state
golden/salead-001.json      Evaluator-only expected outcome
tests/test_mvp.py            Environment and end-to-end tests
```

The `golden/` directory must never be exposed to the system under test.
