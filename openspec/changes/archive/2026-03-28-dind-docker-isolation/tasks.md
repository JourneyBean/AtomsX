## 1. Infrastructure Setup

- [x] 1.1 Add `dind` service to docker-compose.yml with docker:dind image, privileged mode, and DOCKER_TLS_CERTDIR="" environment
- [x] 1.2 Create `dind_data` named volume for dind Docker data persistence
- [x] 1.3 Add health check to dind service using `docker info` command
- [x] 1.4 Configure dind storage driver as `vfs` for MVP simplicity
- [x] 1.5 Remove `/var/run/docker.sock` mount from backend service in docker-compose.yml
- [x] 1.6 Remove `/var/run/docker.sock` mount from celery-worker service in docker-compose.yml
- [x] 1.7 Add dind socket mount to backend service: `/var/run/dind/docker.sock` (from dind volume)
- [x] 1.8 Add dind socket mount to celery-worker service: `/var/run/dind/docker.sock` (from dind volume)
- [x] 1.9 Add `depends_on` with health check condition for backend service to wait for dind
- [x] 1.10 Add `depends_on` with health check condition for celery-worker service to wait for dind
- [x] 1.11 Configure port publishing for dind to expose Workspace preview ports (port range mapping)

## 2. Backend Configuration

- [x] 2.1 Add `DIND_ENABLED` setting to settings.py with default value `true`
- [x] 2.2 Add `DIND_SOCKET_PATH` setting to settings.py with default value `/var/run/dind/docker.sock`
- [x] 2.3 Update `DOCKER_HOST` default value in settings.py to use `DIND_SOCKET_PATH`
- [x] 2.4 Add `DIND_HOST` environment variable support for TCP connection (alternative to socket)
- [x] 2.5 Update .env.example with new dind-related environment variables

## 3. Docker Client Updates

- [x] 3.1 Verify `docker_utils.py` uses `docker.from_env()` (no changes needed if already using)
- [x] 3.2 Add dind health check utility function to `docker_utils.py` for verifying daemon connectivity
- [x] 3.3 Update `WorkspaceContainerManager.__init__` to log connection target for debugging
- [x] 3.4 Add validation in `docker_utils.py` to reject operations if DIND_ENABLED is false

## 4. Celery Task Updates

- [x] 4.1 Verify `tasks.py` uses `docker.from_env()` (no changes needed if already using)
- [x] 4.2 Add dind health check before container operations in `create_workspace_container` task
- [x] 4.3 Add dind health check before container operations in `delete_workspace_container` task
- [x] 4.4 Update error messages to indicate dind connection issues vs Docker operation issues

## 5. Workspace Template Updates

- [x] 5.1 Verify workspace-template Dockerfile build works in dind environment
- [x] 5.2 Update base image build logic in tasks.py to handle dind-specific build context
- [x] 5.3 Ensure workspace-base image is built inside dind (not pulled from host)

## 6. Security Verification

- [x] 6.1 Verify host Docker socket is NOT mounted in any service (except authentik-worker which is unrelated)
- [x] 6.2 Verify backend/celery-worker cannot access `/var/run/docker.sock` (host socket)
- [x] 6.3 Update security tests in `security_tests.py` to verify dind isolation
- [x] 6.4 Add test to verify Workspace containers only exist in dind (not host Docker)
- [x] 6.5 Add test to verify dind socket path configuration override works

## 7. Testing

- [x] 7.1 Write unit test for dind configuration in settings.py
- [x] 7.2 Write integration test for Workspace creation via dind
- [x] 7.3 Write integration test for Workspace deletion via dind
- [x] 7.4 Write test for dind health check failure handling
- [x] 7.5 Write test for port mapping chain (dind → host → gateway)
- [x] 7.6 Verify existing Workspace tests pass with dind configuration
- [x] 7.7 Test full flow: Login → Create Workspace → Start Session → Preview

## 8. Documentation

- [x] 8.1 Update README.md with dind configuration instructions
- [x] 8.2 Document environment variables: DIND_ENABLED, DIND_SOCKET_PATH, DOCKER_HOST
- [x] 8.3 Update architecture diagram to show dind isolation
- [x] 8.4 Document security benefits of dind approach
- [x] 8.5 Document migration path from host Docker to dind

## 9. Monitoring & Auditing

- [x] 9.1 Add audit log for dind connection events (connect, disconnect, health check failure)
- [x] 9.2 Add monitoring metric for dind daemon health status
- [x] 9.3 Add monitoring metric for Workspace container count in dind
- [x] 9.4 Configure alert for dind daemon unavailability