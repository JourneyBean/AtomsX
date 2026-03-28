## ADDED Requirements

### Requirement: uv package manager integration

The backend project SHALL use uv as the primary package manager for dependency management, replacing pip for all dependency operations.

#### Scenario: Install dependencies with uv
- **WHEN** developer runs `uv sync` in backend directory
- **THEN** uv creates a virtual environment and installs all dependencies defined in pyproject.toml
- **AND** uv generates uv.lock file with exact dependency versions

#### Scenario: Add new dependency with uv
- **WHEN** developer runs `uv add <package-name>` in backend directory
- **THEN** uv adds the package to pyproject.toml dependencies
- **AND** uv updates uv.lock with resolved versions
- **AND** uv installs the package in the virtual environment

#### Scenario: Run Python commands in uv environment
- **WHEN** developer runs `uv run <command>` in backend directory
- **THEN** uv executes the command within the managed virtual environment
- **AND** command has access to all installed dependencies

### Requirement: pyproject.toml uv compatibility

The pyproject.toml file SHALL be configured to work seamlessly with uv package manager.

#### Scenario: uv reads dependencies from pyproject.toml
- **WHEN** uv sync is executed
- **THEN** uv reads dependencies from [project.dependencies] section
- **AND** uv reads dev dependencies from [tool.uv.dev-dependencies] or [project.optional-dependencies]

#### Scenario: pyproject.toml maintains setuptools backend
- **WHEN** package needs to be installed via pip
- **THEN** setuptools build backend remains functional
- **AND** pip install . continues to work as fallback

### Requirement: uv.lock file management

The project SHALL maintain uv.lock file in Git version control to ensure reproducible builds.

#### Scenario: uv.lock tracks exact versions
- **WHEN** uv sync is executed with existing uv.lock
- **THEN** uv installs the exact versions specified in uv.lock
- **AND** no version resolution occurs during installation

#### Scenario: uv.lock is updated on dependency change
- **WHEN** developer adds or removes a dependency
- **THEN** uv updates uv.lock with new resolved versions
- **AND** uv.lock must be committed to Git

#### Scenario: frozen build enforces lock file
- **WHEN** `uv sync --frozen` is executed in Docker build
- **THEN** uv fails if uv.lock does not match pyproject.toml
- **AND** prevents accidental version drift in production builds

### Requirement: Docker image build with uv

The backend Docker image SHALL use uv for dependency installation during build process.

#### Scenario: Docker build uses uv for faster installation
- **WHEN** Docker builds backend image
- **THEN** uv binary is copied into the image
- **AND** uv installs dependencies in under 10 seconds (vs 30+ seconds with pip)
- **AND** final image size is comparable to pip-based image

#### Scenario: Docker build uses frozen dependencies
- **WHEN** Docker builds backend image for production
- **THEN** uv sync runs with --frozen flag
- **AND** build fails if uv.lock is outdated
- **AND** ensures reproducible production builds

#### Scenario: Docker build excludes dev dependencies
- **WHEN** Docker builds backend image for production
- **THEN** uv sync runs with --no-dev flag or excludes dev-dependencies
- **AND** production image does not contain pytest, pytest-cov, etc.

### Requirement: Development workflow with uv

The development workflow SHALL use uv commands for all Python dependency operations.

#### Scenario: Run tests with uv
- **WHEN** developer runs `uv run pytest` in backend directory
- **THEN** pytest executes within uv-managed environment
- **AND** all test dependencies are available

#### Scenario: Run Django management commands with uv
- **WHEN** developer runs `uv run python manage.py <command>`
- **THEN** Django management command executes in uv environment
- **AND** Django and all dependencies are available

#### Scenario: Development environment setup
- **WHEN** new developer clones repository and runs `uv sync`
- **THEN** uv creates virtual environment with all dependencies
- **AND** developer can immediately run `uv run pytest` to verify setup

### Requirement: Fallback pip compatibility

The project SHALL maintain pip compatibility as fallback for environments without uv.

#### Scenario: pip install still works
- **WHEN** pip install . is executed in backend directory
- **THEN** setuptools builds and installs the package
- **AND** all dependencies are installed correctly
- **AND** serves as fallback when uv is unavailable