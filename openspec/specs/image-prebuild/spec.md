# Image Prebuild Capability

## Purpose

Enable operators to prebuild workspace images and store them in Docker registry for faster workspace creation.

## Requirements

### Requirement: Operator can prebuild workspace images

The system SHALL provide a Django management command to prebuild workspace images and store them in the Docker registry (dind or host Docker).

#### Scenario: Successful image prebuild
- **WHEN** operator executes `python manage.py prebuild_workspace_images`
- **THEN** system connects to Docker daemon (dind or host based on configuration)
- **AND** system builds or pulls the workspace base image specified in `WORKSPACE_BASE_IMAGE`
- **AND** system stores the image in the target Docker registry
- **AND** system logs the prebuild result with image name and size

#### Scenario: Image prebuild with custom image name
- **WHEN** operator executes `python manage.py prebuild_workspace_images --image custom-workspace:v1`
- **THEN** system builds or pulls the specified custom image
- **AND** system stores the image in the target Docker registry

#### Scenario: Prebuild fails due to Docker daemon unavailable
- **WHEN** operator executes prebuild command but Docker daemon is unavailable
- **THEN** system returns error message "Docker daemon unavailable"
- **AND** system does not modify any existing images

#### Scenario: Prebuild with verbose output
- **WHEN** operator executes `python manage.py prebuild_workspace_images --verbose`
- **THEN** system outputs detailed build/pull progress to console

### Requirement: Prebuild command supports force rebuild

The system SHALL allow operator to force rebuild images even if they already exist.

#### Scenario: Force rebuild existing image
- **WHEN** operator executes `python manage.py prebuild_workspace_images --force`
- **THEN** system removes existing image if present
- **AND** system rebuilds or re-pulls the workspace base image
- **AND** system logs the rebuild action

### Requirement: Prebuild events are audited

The system SHALL record audit logs for all image prebuild operations.

#### Scenario: Successful prebuild audit
- **WHEN** image prebuild completes successfully
- **THEN** system creates audit record with: timestamp, event_type="IMAGE_PREBUILD", image_name, image_size, success=true

#### Scenario: Failed prebuild audit
- **WHEN** image prebuild fails
- **THEN** system creates audit record with: timestamp, event_type="IMAGE_PREBUILD", image_name, error_message, success=false