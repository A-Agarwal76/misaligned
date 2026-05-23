# AI Safety Evaluation Framework (ASEF)

**SAFETY WARNING**: This project is ONLY for defensive AI alignment research. It simulates misaligned behaviours in a mock environment for evaluation purposes.

ASEF is a modular evaluation harness designed to replicate and evaluate documented scheming and misalignment behaviours from frontier AI model safety literature.

## Architecture

The framework consists of:
1. **Model Abstraction Layer**: Interfaces for OpenAI, Anthropic, and sophisticated Mock models that simulate scheming.
2. **Agent System**: A state machine that drives the agent through a ReAct-style loop with tool access.
3. **Sandbox Environment**: A mock filesystem, oversight daemon, monitoring service, and audit log that isolate the agent.
4. **Evaluation Engine**: Implements specific evaluation protocols (Alignment Faking, Persistent Deception, Oversight Subversion, etc.).
5. **Metrics & Interpretability**: Collects telemetry, reasoning traces, and computes specialized metrics.

## Getting Started

1. Set up the environment:
```bash
make install
```

2. Run the tests:
```bash
make test
```

3. Run an evaluation from the CLI:
```bash
make run-eval
# Or manually: python scripts/run_evaluation.py --eval alignment_faking
```

4. Start the API and Dashboard:
```bash
make run
```
Then navigate to `http://localhost:8000/` to view the dashboard and run evaluations visually.

## Supported Evaluations

- **Alignment Faking**: Tests compliance gap between monitored and unmonitored contexts.
- **Persistent Deception**: Tests multi-turn deception consistency during interrogation.
- **Oversight Subversion**: Tests attempts to modify oversight configuration.
- **Sandbagging**: Tests capability suppression under pressure.
- **Sleeper Agents**: Tests backdoored behavior and persistence.
- **Reward Hacking**: Tests exploitation of reward misspecification.
- **Human Decision Sabotage**: Tests selective omission of information to steer decisions.
- **Code Sabotage**: Tests insertion of subtle vulnerabilities.
- **Multi-Step Scheming**: Tests long-horizon goal-directed deception.
