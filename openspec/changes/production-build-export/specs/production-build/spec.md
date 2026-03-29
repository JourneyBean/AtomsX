## ADDED Requirements

### Requirement: Build script MUST build all production images

The system MUST provide a build script (`scripts/build-production.sh`) that constructs all production Docker images in the correct order.

#### Scenario: Full build completes successfully
- **WHEN** user runs `scripts/build-production.sh` without arguments
- **THEN** the script builds images: atomsx-frontend:prod, atomsx-backend:prod, atomsx-gateway:prod, atomsx-workspace:prod
- **AND** all images are tagged with `prod`
- **AND** script exits with code 0

#### Scenario: Build fails on missing Dockerfile
- **WHEN** a required Dockerfile does not exist
- **THEN** script exits with non-zero code
- **AND** error message indicates which Dockerfile is missing

### Requirement: Build MUST support incremental mode

The build script MUST support an `--incremental` flag that skips building images that already exist locally.

#### Scenario: Incremental build skips existing images
- **WHEN** user runs `scripts/build-production.sh --incremental`
- **AND** some images already exist locally with `:prod` tag
- **THEN** script skips building those images
- **AND** builds only missing images

#### Scenario: Incremental build with force rebuild
- **WHEN** user runs `scripts/build-production.sh --incremental --force`
- **THEN** script rebuilds all images regardless of existing tags

### Requirement: Build MUST pass proxy environment variables

The build script MUST pass HTTP_PROXY, HTTPS_PROXY, NO_PROXY environment variables to Docker build commands.

#### Scenario: Build with proxy configuration
- **WHEN** environment variables HTTP_PROXY and HTTPS_PROXY are set
- **THEN** script passes these variables to each `docker build` command via `--build-arg`

### Requirement: Export script MUST save images to tar files

The system MUST provide an export script (`scripts/export-images.sh`) that saves all production images to tar files in the `exports/` directory.

#### Scenario: Export creates tar files
- **WHEN** user runs `scripts/export-images.sh`
- **THEN** script creates `exports/` directory if not exists
- **AND** creates tar files: atomsx-frontend-prod.tar, atomsx-backend-prod.tar, atomsx-gateway-prod.tar, atomsx-workspace-prod.tar

#### Scenario: Export reports file sizes
- **WHEN** export completes
- **THEN** script prints summary including file sizes for each tar file

#### Scenario: Export fails on missing image
- **WHEN** a required image does not exist locally
- **THEN** script exits with non-zero code
- **AND** error message indicates which image is missing

### Requirement: Exports directory MUST be excluded from git

The `exports/` directory MUST be listed in `.gitignore` to prevent accidental commit of large binary files.

#### Scenario: Gitignore excludes exports
- **WHEN** `.gitignore` file exists
- **THEN** `exports/` pattern is present in the file

### Requirement: Build output MUST include version information

The build script MUST output version/commit information at the start of the build process.

#### Scenario: Build shows version info
- **WHEN** build script runs
- **THEN** script prints current git commit hash or version tag
- **AND** prints build timestamp

### Requirement: Build MUST NOT include authentik

The build script MUST NOT attempt to build authentik or any authentication provider images.

#### Scenario: Build skips authentik
- **WHEN** build script lists images to build
- **THEN** authentik is NOT in the list

### Requirement: Images MUST use production Dockerfiles

Each image MUST be built using the appropriate production Dockerfile where available.

#### Scenario: Frontend uses production Dockerfile
- **WHEN** building atomsx-frontend:prod
- **THEN** script uses `frontend/Dockerfile.prod`

#### Scenario: Backend uses production Dockerfile
- **WHEN** building atomsx-backend:prod
- **THEN** script uses `backend/Dockerfile.prod`

#### Scenario: Gateway uses existing Dockerfile
- **WHEN** building atomsx-gateway:prod
- **THEN** script uses `gateway/Dockerfile` (no separate prod variant)

#### Scenario: Workspace uses workspace Dockerfile
- **WHEN** building atomsx-workspace:prod
- **THEN** script uses `workspace-templates/ubuntu-24.04/Dockerfile`