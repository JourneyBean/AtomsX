## 1. pyproject.toml Configuration

- [x] 1.1 Update pyproject.toml with uv-compatible configuration
- [x] 1.2 Add [tool.uv] section for uv-specific settings
- [x] 1.3 Configure dev dependencies under [project.optional-dependencies] (uv reads this)
- [x] 1.4 Verify setuptools backend remains for pip fallback compatibility
- [x] 1.5 Add [tool.ruff] section placeholder for future linting (optional)

## 2. uv.lock Generation

- [x] 2.1 Install uv locally (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [x] 2.2 Run `uv sync` to generate uv.lock file
- [x] 2.3 Verify uv.lock contains all dependencies with exact versions
- [x] 2.4 Add uv.lock to Git version control

## 3. Dockerfile Refactor

- [x] 3.1 Add COPY instruction to copy uv binary from official image
- [x] 3.2 Update dependency installation to use `uv sync --frozen --no-dev`
- [x] 3.3 Copy pyproject.toml and uv.lock before application code (layer caching)
- [x] 3.4 Verify production build excludes dev dependencies (pytest, pytest-cov)
- [x] 3.5 Test Docker build locally and measure build time improvement

## 4. Development Workflow Documentation

- [x] 4.1 Add uv installation instructions to README or dev docs
- [x] 4.2 Document common commands: `uv sync`, `uv add`, `uv run`
- [x] 4.3 Document test execution: `uv run pytest`
- [x] 4.4 Document Django management commands: `uv run python manage.py`
- [x] 4.5 Add troubleshooting section for common uv issues

## 5. Verification & Testing

- [ ] 5.1 Run `uv run pytest` to verify all tests pass in uv environment
- [ ] 5.2 Run `uv run python manage.py check` to verify Django configuration
- [ ] 5.3 Verify `pip install .` still works as fallback
- [ ] 5.4 Verify Docker build produces working image
- [ ] 5.5 Compare Docker build time before/after migration

## 6. Cleanup

- [ ] 6.1 Remove any pip-specific configuration that conflicts with uv
- [ ] 6.2 Verify no stray requirements.txt files remain
- [ ] 6.3 Update any CI/CD references (if exists) to use uv commands