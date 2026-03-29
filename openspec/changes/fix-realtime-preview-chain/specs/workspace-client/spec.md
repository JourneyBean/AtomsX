## MODIFIED Requirements

### Requirement: Claude Agent receives environment context

The system SHALL provide environment context to Claude Agent via `system_prompt` configuration, informing Claude about the container environment, correct path usage, and preview capabilities.

#### Scenario: Claude uses correct workspace path
- **WHEN** Claude Agent is asked to create or modify a file
- **THEN** Claude uses a path under `/home/user/workspace`
- **AND** the file is created in the correct location

#### Scenario: Claude avoids hallucinated paths
- **WHEN** Claude Agent needs to reference a file path
- **THEN** Claude uses paths starting with `/home/user/workspace` or relative paths
- **AND** Claude does NOT use paths like `/Users/...` or other host-specific patterns

#### Scenario: Claude understands preview capabilities
- **WHEN** Claude Agent is asked to show preview or run development server
- **THEN** Claude knows to create start_app.sh in workspace directory
- **AND** Claude knows preview server must listen on 0.0.0.0:3000
- **AND** Claude can provide appropriate start commands for common frameworks

## ADDED Requirements

### Requirement: Environment context includes preview guidance

The system SHALL include preview-related guidance in the environment context provided to Claude Agent.

#### Scenario: New session includes preview context
- **WHEN** a new session is created via `start_session()`
- **THEN** the Claude Agent options include `system_prompt` with:
  - Preview port information (3000)
  - Instructions for creating start_app.sh
  - Common framework start commands
  - Requirement to listen on 0.0.0.0 (not localhost only)

#### Scenario: Resumed session includes preview context
- **WHEN** a session is resumed via `resume_session()`
- **THEN** the Claude Agent options include `system_prompt` with preview guidance
- **AND** Claude maintains consistent understanding of preview capabilities

### Requirement: workspace-client runs under supervisord

The system SHALL run workspace-client as a supervised process managed by supervisord, not as the main container process.

#### Scenario: workspace-client supervised process
- **WHEN** workspace container starts
- **THEN** supervisord is PID 1
- **AND** workspace-client is a child process of supervisord
- **AND** workspace-client auto-restarts on failure

#### Scenario: workspace-client logs captured
- **WHEN** workspace-client produces output
- **THEN** stdout is written to /home/user/logs/workspace-client.log
- **AND** stderr is written to /home/user/logs/workspace-client-error.log