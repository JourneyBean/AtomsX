# Implementation Tasks

## 1. Django Configuration

- [x] 1.1 Add `WORKSPACE_DATA_ROOT` configuration to Django settings module
- [x] 1.2 Add environment variable `ATOMSX_WORKSPACE_DATA_ROOT` support with default `/var/opt/atomsx/workspaces`
- [x] 1.3 Add `data_dir_path` field to Workspace model for storing computed data directory path
- [x] 1.4 Add database migration for Workspace model `data_dir_path` field

## 2. Path Computation Utility

- [x] 2.1 Create `compute_user_data_path(uuid: str, root: str)` utility function
- [x] 2.2 Implement UUID sharding logic: extract first and second characters from UUID
- [x] 2.3 Return path format: `{root}/{uuid[0]}/{uuid[1]}/{uuid}/`
- [x] 2.4 Add unit tests for path computation with various UUID formats
- [x] 2.5 Add validation for UUID format (raise exception for invalid UUID)

## 3. Celery Task: Create User Data Directory

- [x] 3.1 Create Celery task `create_user_data_directory(workspace_id: str)`
- [x] 3.2 Retrieve Workspace record and compute data directory path
- [x] 3.3 Create sharded directory structure using `os.makedirs(..., mode=0o755)`
- [x] 3.4 Create `workspace/` and `history/` subdirectories
- [x] 3.5 Handle permission denied error: update Workspace status to "error" with error message
- [x] 3.6 Handle disk full error: update Workspace status to "error" with error message
- [x] 3.7 Create audit record on directory creation failure with `event_type="WORKSPACE_ERROR"`
- [x] 3.8 Update Workspace record with `data_dir_path` after successful creation

## 4. Celery Task: Create Workspace Container

- [x] 4.1 Modify existing `create_workspace_container` task to call `create_user_data_directory` first
- [x] 4.2 Add Docker bind mount configuration: `{data_dir_path}` → `/home/user`
- [x] 4.3 Ensure mount uses `type=bind` in Docker API call
- [x] 4.4 Include `data_dir_path` in audit record for `event_type="WORKSPACE_CREATED"`
- [x] 4.5 Handle existing data directory case: reuse without recreating subdirectories

## 5. Celery Task: Delete Workspace Container

- [x] 5.1 Modify existing `delete_workspace_container` task to NOT delete data directory
- [x] 5.2 Ensure only container is removed, data directory remains on host
- [x] 5.3 Update audit record to clarify: container deleted, data preserved

## 6. Django API: Workspace Detail View

- [x] 6.1 Update Workspace detail serializer to include `data_dir_path` field
- [x] 6.2 Return `data_dir_path` in GET `/api/workspaces/{id}/` response

## 7. Error Handling & Audit

- [x] 7.1 Add custom exception `UserDataDirectoryError` with reason field
- [x] 7.2 Ensure all directory creation errors are caught and wrapped
- [x] 7.3 Add logging for directory creation success/failure
- [x] 7.4 Verify audit records include `data_dir_path` for all Workspace events

## 8. Testing

- [ ] 8.1 Add integration test for Workspace creation with data directory creation
- [ ] 8.2 Add integration test for Workspace deletion preserving data directory
- [ ] 8.3 Add integration test for Workspace recreation reusing existing data directory
- [ ] 8.4 Add test for permission denied error handling
- [ ] 8.5 Add test for custom `ATOMSX_WORKSPACE_DATA_ROOT` environment variable
- [ ] 8.6 Add test for UUID sharding structure correctness

> **Note**: Tests written but skipped due to pytest-django configuration issue. Test code exists in `apps/workspaces/tests.py`.

## 9. Development Environment Setup

- [x] 9.1 Create `./dev-cache/data/` directory structure for development
- [x] 9.2 Add `.gitignore` entry for `dev-cache/` directory
- [x] 9.3 Verify development environment uses docker compose mount `.dev-cache/docker/atomsx:/var/opt/atomsx`

## 10. Documentation & Monitoring

- [x] 10.1 Add environment variable documentation for `ATOMSX_WORKSPACE_DATA_ROOT`
- [x] 10.2 Add log metric for data directory creation count
- [x] 10.3 Add log metric for data directory creation failures
- [x] 10.4 Document data directory structure and sharding rationale in README or docs