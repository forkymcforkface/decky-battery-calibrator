# Contributing to Battery Calibrator

Thanks for your interest in contributing! This guide explains how to develop, test, and submit changes.

## Development Setup

### Prerequisites
- Node.js v22.14+
- pnpm 11.x
- Python 3.13+
- uv (Python package manager)
- Decky Loader running on Steam Deck

### Clone & Install

```bash
git clone https://github.com/Yogendra96/decky-battery-calibrator.git
cd decky-battery-calibrator
pnpm install
```

### Building

```bash
# Development build (watch mode)
pnpm run watch

# Production build
pnpm run build
```

### Testing

```bash
# Run all tests
~/.local/bin/pytest tests/ -v

# Run specific test file
~/.local/bin/pytest tests/test_calibration.py -v

# Run with coverage
~/.local/bin/pytest tests/ --cov=py_modules/battery_calibrator

# Linting
ruff check py_modules/ tests/ main.py

# Type checking
pyright py_modules/ main.py
```

## Code Style

### Python
- Follow PEP 8 (enforced by ruff)
- Type hints on all function signatures
- Docstrings on public classes/methods
- Use asyncio for I/O (never `time.sleep`)

### TypeScript/React
- Use TypeScript (no `.js` files)
- Optional chaining `?.` for null safety
- Nullish coalescing `??` for defaults
- Functional components only (no class components)

### Git Commit Messages
```
feat: Add feature X
fix: Fix bug Y
docs: Update README
refactor: Split frontend components
test: Add tests for calibration FSM

- Include imperative mood ("add" not "adds")
- Reference issues/PRs if applicable
```

## Adding Features

### 1. Backend Feature (Python)

1. Create method in appropriate module (`battery.py`, `calibration.py`, etc.)
2. Add RPC callable in `main.py`:
   ```python
   async def my_rpc_method(self, arg: int) -> bool:
       return await self.some_component.do_something(arg)
   ```
3. Write tests in `tests/test_*.py` (mock dependencies)
4. Run full test suite: `pytest tests/`

### 2. Frontend Feature (React/TypeScript)

1. Add RPC callable declaration in `src/index.tsx`:
   ```typescript
   const myRPC = callable<[arg: number], boolean>("my_rpc_method");
   ```
2. Wrap in `safe()`:
   ```typescript
   const result = await safe(() => myRPC(42), false);
   ```
3. Add null checks with `?.` and `??`:
   ```typescript
   {result?.data ?? "Loading..."}
   ```
4. Build and test: `pnpm run build`

## Testing on Hardware

### Deploy to Steam Deck

```bash
make dev-deploy
```

This builds, copies to Decky plugins directory, and restarts the plugin.

### Manual Testing Checklist

- [ ] Feature loads without errors
- [ ] Feature visible in QAM (quick access menu)
- [ ] Click every button, test every slider
- [ ] Check journalctl for errors: `journalctl -u decky-loader -f`
- [ ] Test edge cases (unplug during calibration, etc.)

## Reporting Issues

### Bug Reports
Include:
- SteamOS version (Settings → System)
- Exact steps to reproduce
- Expected vs. actual behavior
- Logs: `journalctl -u decky-loader -n 50`

### Feature Requests
- Explain the use case
- Describe how it would work
- Consider: does it align with project scope?

## Release Process

1. Update version in `package.json` and `plugin.json`
2. Update `CHANGELOG.md` (if you create one)
3. Create git tag: `git tag v1.1.0`
4. Push: `git push origin main --tags`
5. Create GitHub release with build instructions

## Architecture & Design

See:
- `ARCHITECTURE.md` — System design and why we made decisions
- `KNOWN_LIMITATIONS.md` — Hardware and software constraints
- `REFACTORING_NOTES.md` — Future plans for v1.1

## Questions?

- Check `ARCHITECTURE.md` first
- Look at existing code for examples
- Open an issue to discuss larger changes

Thanks for contributing! 🚀
