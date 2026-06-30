# Contributing

Thank you for your interest in AsyncViz. Contributions of every size are welcome, including bug reports, feature requests, documentation improvements, additional tests, performance improvements, and pull requests. AsyncViz is preparing its first public release, so feedback from early users is particularly valuable.

---

## Development Setup

Clone the repository and create an isolated Python environment:

```bash
git clone https://github.com/geghamjivanyan/asyncviz.git
cd asyncviz

python -m venv .venv
source .venv/bin/activate

pip install -e ".[all]"
```

The `all` extra installs everything required for development, including the test runner, the linter, build tools, and packaging utilities. It is the recommended starting point for contributors.

---

## Running the Frontend

The dashboard SPA lives under `frontend/` and is built with Vite. During development it is served by the Vite dev server with hot module reloading:

```bash
cd frontend
npm install
npm run dev
```

---

## Running AsyncViz

There are two supported ways to exercise the runtime end-to-end:

The minimal public example:

```bash
python examples/basic/app.py
```

This is the smallest workload that lights up every dashboard page and is the recommended starting point for new contributors.

The internal validation workload:

```bash
asyncviz run validation/mega_runtime.py
```

This is a richer, intentionally varied workload used internally to validate AsyncViz under more demanding runtime conditions. It is not intended as a supported public example.

---

## Running Tests

The backend test suite is driven by pytest:

```bash
pytest
```

The frontend has its own Vitest suite:

```bash
cd frontend
npm test
```

Type checking the frontend:

```bash
cd frontend
npm run typecheck
```

Building distribution artifacts and verifying their metadata:

```bash
python -m build
twine check dist/*
```

---

## Coding Guidelines

- Follow the existing style of the file you are editing.
- Keep changes focused. Smaller pull requests are easier to review and ship.
- Prefer readable, straightforward implementations over clever ones.
- Add or update tests when introducing new behavior or fixing a bug.
- Update documentation whenever user-facing behavior changes.
- Avoid breaking the public API unless absolutely necessary, and call out any deliberate break in the pull request description.

---

## Pull Requests

Before opening a pull request, please ensure:

- All tests pass (`pytest` and `npm test`).
- No linting or type-checking errors remain. Please run the project's linting and type-checking tools before submitting a pull request.
- Documentation has been updated where necessary.
- UI changes include refreshed screenshots or GIFs when the visual change is meaningful.
- Commit history is reasonably clean. Squash or rebase noisy intermediate commits before requesting review.

A clear pull request description that explains the motivation, the approach, and any trade-offs makes review significantly faster.

---

## Reporting Issues

When opening a bug report, please include:

- AsyncViz version.
- Python version.
- Operating system.
- A minimal reproducible example.
- The error message or traceback, if applicable.

Bug reports and feature requests should be filed through [GitHub Issues](https://github.com/geghamjivanyan/asyncviz/issues). Please search existing issues before opening a new one.

---

## Questions

If you are unsure whether a larger feature fits the project's direction, please open a GitHub Issue describing the idea before starting work. Early discussion saves time on both sides and helps ensure your contribution can be merged.

---

## License

By contributing to AsyncViz, you agree that your contributions will be licensed under the project's MIT License.
