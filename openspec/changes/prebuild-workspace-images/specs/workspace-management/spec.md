## MODIFIED Requirements

### Requirement: Workspace creation timeout is configurable

The system SHALL provide configurable timeout settings for workspace container creation tasks.

#### Scenario: Default timeout configuration
- **WHEN** no custom timeout is configured
- **THEN** system uses default soft time limit of 300 seconds (5 minutes)
- **AND** system uses default hard time limit of 360 seconds (6 minutes)

#### Scenario: Custom timeout via environment variables
- **WHEN** environment variable `WORKSPACE_CREATION_SOFT_TIMEOUT` is set to custom value (e.g., 600)
- **THEN** system uses the custom soft time limit value
- **AND** workspace creation task respects the custom timeout

#### Scenario: Custom timeout via Django settings
- **WHEN** Django setting `WORKSPACE_CREATION_TIME_LIMITS` is configured with custom values
- **THEN** system uses the configured soft and hard time limits
- **AND** environment variable takes precedence if both are set

### Requirement: User can create a new Workspace

The system SHALL allow logged-in users to create a new isolated Workspace container with optimized image retrieval and configurable timeout constraints.

#### Scenario: Successful Workspace creation
- **WHEN** logged-in user submits Workspace creation request with name
- **THEN** system validates the name is non-empty and within length limit (max 100 characters)
- **AND** system creates Workspace record in database with: id (UUID), owner (user), name, status="creating", created_at
- **AND** system triggers asynchronous container creation task with configurable soft time limit
- **AND** system returns HTTP 201 Created with Workspace metadata

#### Scenario: Workspace container creation with prebuilt image
- **WHEN** container creation task starts and prebuilt image exists in Docker registry
- **THEN** system uses the prebuilt image directly without pulling
- **AND** system creates Docker container with isolated network and volume
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED", image_source="prebuilt"

#### Scenario: Workspace container creation without prebuilt image
- **WHEN** container creation task starts and prebuilt image does not exist
- **THEN** system attempts to pull fallback image (node:20-slim)
- **AND** system creates Docker container with fallback image
- **AND** system stores container_id in Workspace record
- **AND** system updates Workspace status to "running"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_CREATED", image_source="fallback_pull"

#### Scenario: Workspace creation exceeds configurable soft time limit
- **WHEN** container creation task exceeds configured soft time limit
- **THEN** task receives SoftTimeLimitExceeded exception
- **AND** system updates Workspace status to "error"
- **AND** system records error message "Workspace creation timeout exceeded (soft limit: {configured_value}s)"
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message="timeout"

#### Scenario: Workspace creation exceeds configurable hard time limit
- **WHEN** container creation task exceeds configured hard time limit
- **THEN** task is forcibly terminated by Celery
- **AND** system detects orphaned Workspace in "creating" status on subsequent checks
- **AND** system updates Workspace status to "error" with message "Task terminated due to timeout (hard limit: {configured_value}s)"

#### Scenario: Workspace container creation fails
- **WHEN** container creation task fails (e.g., Docker unavailable, resource limit)
- **THEN** system updates Workspace status to "error"
- **AND** system records error message in Workspace record
- **AND** system creates audit record with: timestamp, user_id, workspace_id, event_type="WORKSPACE_ERROR", error_message

#### Scenario: Duplicate Workspace name for same user
- **WHEN** user attempts to create Workspace with name that already exists for that user
- **THEN** system returns HTTP 409 Conflict with error message "Workspace name already exists"