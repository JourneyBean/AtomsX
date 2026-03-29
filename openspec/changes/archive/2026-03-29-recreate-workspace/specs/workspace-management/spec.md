## ADDED Requirements

### Requirement: Workspace status includes recreating state

The system SHALL support a `recreating` status for Workspace, indicating the workspace container is being rebuilt with the latest image.

#### Scenario: Valid recreating status transitions
- **WHEN** workspace status is `running`, `stopped`, or `error`
- **THEN** system allows transition to `recreating` status
- **AND** system does not allow transition from `creating` or `deleting` to `recreating`

#### Scenario: Recreating status to running
- **WHEN** recreate task completes successfully
- **THEN** system transitions workspace status from `recreating` to `running`

#### Scenario: Recreating status to error
- **WHEN** recreate task fails (timeout, Docker error, image not found)
- **THEN** system transitions workspace status from `recreating` to `error`
- **AND** system records error message in workspace record

### Requirement: User can recreate a Workspace

The system SHALL allow logged-in users to recreate a Workspace they own, replacing its container with a new one using the latest prebuilt image while preserving the data directory.

#### Scenario: Successful Workspace recreate from running state
- **WHEN** logged-in user requests recreate on a workspace with status `running`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Successful Workspace recreate from stopped state
- **WHEN** logged-in user requests recreate on a workspace with status `stopped`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task (creates new container since old one does not exist)
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Successful Workspace recreate from error state
- **WHEN** logged-in user requests recreate on a workspace with status `error`
- **THEN** system validates workspace ownership
- **AND** system updates workspace status to `recreating`
- **AND** system triggers asynchronous recreate task
- **AND** system returns HTTP 202 Accepted with workspace metadata

#### Scenario: Recreate task execution
- **WHEN** recreate task starts
- **THEN** system stops old container (if exists) with timeout of 10 seconds
- **AND** system removes old container (if exists)
- **AND** system deletes old WorkspaceToken
- **AND** system creates new WorkspaceToken
- **AND** system creates new container with same `data_dir_path` bind mounts
- **AND** system starts new container
- **AND** system updates workspace `container_id` to new container ID
- **AND** system updates workspace status to `running`
- **AND** system creates audit record with: timestamp, user_id, workspace_id, container_id, event_type="WORKSPACE_RECREATED"

#### Scenario: Recreate preserves data directory
- **WHEN** recreate task creates new container
- **THEN** system uses the same `data_dir_path` from workspace record
- **AND** system mounts `/home/user/workspace` to same host path
- **AND** system mounts `/home/user/history` to same host path
- **AND** workspace files and history data are preserved

#### Scenario: Recreate other user's Workspace forbidden
- **WHEN** logged-in user requests recreate on workspace owned by another user
- **THEN** system returns HTTP 403 Forbidden
- **AND** system does not change workspace status

#### Scenario: Recreate on deleting workspace forbidden
- **WHEN** logged-in user requests recreate on workspace with status `deleting`
- **THEN** system returns HTTP 400 Bad Request with error message "Cannot recreate workspace in deleting state"

#### Scenario: Recreate on recreating workspace conflict
- **WHEN** logged-in user requests recreate on workspace with status `recreating`
- **THEN** system returns HTTP 409 Conflict with error message "Workspace recreate already in progress"

#### Scenario: Recreate with prebuilt image not found
- **WHEN** recreate task starts and prebuilt image does not exist in Docker registry
- **THEN** system updates workspace status to `error`
- **AND** system records error message "Workspace image not found"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="image_not_found"

#### Scenario: Recreate exceeds soft time limit
- **WHEN** recreate task exceeds configurable soft time limit
- **THEN** task receives SoftTimeLimitExceeded exception
- **AND** system updates workspace status to `error`
- **AND** system records error message "Workspace recreate timeout exceeded"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="timeout"

#### Scenario: Recreate with Docker error
- **WHEN** recreate task encounters Docker operation error (container creation fails)
- **THEN** system updates workspace status to `error`
- **AND** system records error message from Docker exception
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

### Requirement: Workspace recreate events are audited

The system SHALL record audit logs for Workspace recreate events.

#### Scenario: Recreate success audit
- **WHEN** Workspace recreate completes successfully
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, container_id (new), event_type="WORKSPACE_RECREATED"
- **AND** audit record includes previous_container_id if available

#### Scenario: Recreate error audit
- **WHEN** Workspace recreate fails
- **THEN** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message