## 1. Backend Models

- [x] 1.1 Add `recreating` to `Workspace.STATUS_CHOICES` in `backend/apps/workspaces/models.py`
- [x] 1.2 Update `Workspace.transition_status()` to allow `recreating` transitions: running→recreating, stopped→recreating, error→recreating, recreating→running, recreating→error

## 2. Backend Celery Task

- [x] 2.1 Create `recreate_workspace_container()` Celery task in `backend/apps/workspaces/tasks.py`
- [x] 2.2 Implement container stop logic (timeout=10s) with fallback for non-existent container
- [x] 2.3 Implement container removal and WorkspaceToken cleanup
- [x] 2.4 Implement new container creation with same `data_dir_path` bind mounts
- [x] 2.5 Add soft/hard time limit configuration (reuse `WORKSPACE_CREATION_SOFT_TIMEOUT/HARD_TIMEOUT`)
- [x] 2.6 Add error handling for image not found, Docker errors, timeout
- [x] 2.7 Add audit log for `WORKSPACE_RECREATED` event with old and new container_id

## 3. Backend API

- [x] 3.1 Create `WorkspaceRecreateView` in `backend/apps/workspaces/views.py`
- [x] 3.2 Implement ownership validation (403 for non-owner)
- [x] 3.3 Implement status validation (400 for deleting, 409 for recreating)
- [x] 3.4 Trigger `recreate_workspace_container` task and return 202 Accepted
- [x] 3.5 Add route `POST /api/workspaces/<uuid:workspace_id>/recreate/` in `backend/apps/workspaces/urls.py`

## 4. Frontend Types

- [x] 4.1 Add `recreating` to `Workspace.status` type in `frontend/src/types/index.ts`

## 5. Frontend UI

- [x] 5.1 Add `recreateWorkspace()` function in `frontend/src/views/WorkspaceListView.vue`
- [x] 5.2 Add Recreate button to workspace card (visible for running, stopped, error status)
- [x] 5.3 Implement button state: "Recreating..." when status=recreating, disabled during operation
- [x] 5.4 Update workspace list after recreate completes (polling or refresh)

## 6. Audit

- [x] 6.1 Add `WORKSPACE_RECREATED` event type handling in audit log system
- [x] 6.2 Ensure recreate error creates audit record with `WORKSPACE_ERROR` event type

## 7. Testing

- [x] 7.1 Verify recreate from running state: container replaced, data preserved
- [x] 7.2 Verify recreate from stopped state: new container created, data preserved
- [x] 7.3 Verify recreate from error state: recovery successful
- [x] 7.4 Verify recreate forbidden for non-owner (403)
- [x] 7.5 Verify recreate conflict when already recreating (409)
- [x] 7.6 Verify recreate error when image not found

## 8. Spec Sync

- [x] 8.1 Sync delta spec to main spec: `openspec/specs/workspace-management/spec.md`
- [ ] 8.2 Archive change after implementation complete