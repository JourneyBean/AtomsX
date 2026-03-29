# Workspace Client Capability

## ADDED Requirements

### Requirement: Claude Agent SDK uses bypassPermissions mode

The system SHALL configure Claude Agent SDK with `permission_mode: "bypassPermissions"` to allow all tool calls to execute without user confirmation.

#### Scenario: Tool call executes automatically
- **WHEN** Claude Agent attempts to use a tool (Write, Edit, Bash, etc.)
- **THEN** the tool executes immediately without prompting for user approval
- **AND** the tool result is returned to Claude for continued processing

#### Scenario: Multiple tools execute in sequence
- **WHEN** Claude Agent uses multiple tools in a single turn
- **THEN** all tools execute in sequence without user intervention
- **AND** all tool results are streamed back to the frontend

### Requirement: Claude Agent receives environment context

The system SHALL provide environment context to Claude Agent via `system_prompt` configuration, informing Claude about the container environment and correct path usage.

#### Scenario: Claude uses correct workspace path
- **WHEN** Claude Agent is asked to create or modify a file
- **THEN** Claude uses a path under `/home/user/workspace`
- **AND** the file is created in the correct location

#### Scenario: Claude avoids hallucinated paths
- **WHEN** Claude Agent needs to reference a file path
- **THEN** Claude uses paths starting with `/home/user/workspace` or relative paths
- **AND** Claude does NOT use paths like `/Users/...` or other host-specific patterns

### Requirement: Environment context is included in session creation

The system SHALL include the following environment context in the system prompt when creating or resuming a session:

- Working directory: `/home/user/workspace`
- User data directory: `/home/user/data` (if applicable)
- Path usage guidelines and examples

#### Scenario: New session includes environment context
- **WHEN** a new session is created via `start_session()`
- **THEN** the Claude Agent options include `system_prompt` with environment context
- **AND** Claude understands it is running in a container environment

#### Scenario: Resumed session includes environment context
- **WHEN** a session is resumed via `resume_session()`
- **THEN** the Claude Agent options include `system_prompt` with environment context
- **AND** Claude maintains consistent understanding of the environment