## 1. Django Management Command Setup

- [x] 1.1 Create management command directory structure (`backend/apps/workspaces/management/commands/`)
- [x] 1.2 Create `prebuild_workspace_images.py` management command file
- [x] 1.3 Implement Docker client connection with dind/host detection
- [x] 1.4 Implement image build/pull logic with `WORKSPACE_BASE_IMAGE` setting
- [x] 1.5 Add `--image` argument for custom image name support
- [x] 1.6 Add `--force` argument for force rebuild support
- [x] 1.7 Add `--verbose` argument for detailed output support
- [x] 1.8 Add error handling for Docker daemon unavailable scenario

## 2. Configurable Timeout Settings

- [x] 2.1 Add `WORKSPACE_CREATION_SOFT_TIMEOUT` setting to `settings.py` with environment variable support (default 300s)
- [x] 2.2 Add `WORKSPACE_CREATION_HARD_TIMEOUT` setting to `settings.py` with environment variable support (default 360s)
- [x] 2.3 Update `create_workspace_container` task decorator to use configurable timeout values from settings
- [x] 2.4 Add SoftTimeLimitExceeded exception handling in `create_workspace_container`
- [x] 2.5 Update Workspace error handling to include actual timeout values in error messages
- [x] 2.6 Document timeout configuration options and recommended values

## 3. Workspace Creation Task Optimization

- [x] 3.1 Refactor image retrieval logic in `create_workspace_container` task
- [x] 3.2 Implement prebuilt image detection (check if image exists before fallback pull)
- [x] 3.3 Add `image_source` field to audit log for workspace creation events
- [x] 3.4 Maintain fallback pull logic for non-prebuilt scenarios
- [x] 3.5 Ensure backward compatibility with existing workspace creation flow

## 4. Audit Logging

- [x] 4.1 Create audit log entry for successful prebuild events (`IMAGE_PREBUILD` with image details)
- [x] 4.2 Create audit log entry for failed prebuild events (with error message)
- [x] 4.3 Update workspace creation audit to include `image_source` field

## 5. Testing

- [x] 5.1 Write unit tests for `prebuild_workspace_images` command
- [x] 5.2 Write test for successful prebuild scenario
- [x] 5.3 Write test for prebuild with custom image argument
- [x] 5.4 Write test for force rebuild scenario
- [x] 5.5 Write test for Docker daemon unavailable error handling
- [x] 5.6 Write test for configurable timeout default values
- [x] 5.7 Write test for configurable timeout via environment variables
- [x] 5.8 Write test for Celery timeout handling in workspace creation
- [x] 5.9 Write test for prebuilt image usage in workspace creation
- [x] 5.10 Write test for fallback pull scenario when prebuilt image missing

## 6. Documentation and Verification

- [x] 6.1 Add usage documentation for `prebuild_workspace_images` command in README or docs
- [x] 6.2 Document timeout configuration options (`WORKSPACE_CREATION_SOFT_TIMEOUT`, `WORKSPACE_CREATION_HARD_TIMEOUT`)
- [x] 6.3 Document deployment steps including prebuild command execution
- [x] 6.4 Verify prebuild command works in development environment (host Docker)
- [ ] 6.5 Verify prebuild command works in production-like environment (dind)
- [ ] 6.6 Verify configurable timeout settings work correctly
- [ ] 6.7 Measure workspace creation time before and after optimization