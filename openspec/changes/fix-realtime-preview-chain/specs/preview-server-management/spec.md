## ADDED Requirements

### Requirement: Preview server starts automatically when workspace container launches

The system SHALL automatically start a preview server process when the workspace container starts, ensuring port 3000 is always serving content.

#### Scenario: Preview server starts with container
- **WHEN** workspace container is created and starts
- **THEN** supervisord starts preview-server process
- **AND** preview-server listens on port 3000
- **AND** process is configured to auto-restart on failure

#### Scenario: Preview server auto-restarts on crash
- **WHEN** preview-server process crashes or exits unexpectedly
- **THEN** supervisord automatically restarts the process within 5 seconds
- **AND** process restart is logged to /home/user/logs/preview-server.log

### Requirement: Preview server executes user start_app.sh script if present

The system SHALL execute the user-provided start_app.sh script from the workspace directory when it exists, allowing custom preview server configuration.

#### Scenario: start_app.sh exists and executes successfully
- **WHEN** /home/user/workspace/start_app.sh exists and is executable
- **THEN** system executes the script
- **AND** script output is logged to /home/user/logs/preview-server.log
- **AND** preview server runs on port 3000

#### Scenario: start_app.sh exists but fails to execute
- **WHEN** /home/user/workspace/start_app.sh exists but fails (non-zero exit code)
- **THEN** system starts placeholder server on port 3000
- **AND** placeholder returns JSON with status "placeholder" and message "start_failed"
- **AND** error details from start_app.sh are included in the response
- **AND** error is logged to /home/user/logs/preview-server.log

#### Scenario: start_app.sh has wrong permissions
- **WHEN** /home/user/workspace/start_app.sh exists but is not executable
- **THEN** system attempts to make it executable
- **AND** if successful, proceeds to execute it
- **AND** if unsuccessful, starts placeholder server with "permission_denied" message

### Requirement: Placeholder server runs when no start_app.sh exists

The system SHALL run a placeholder HTTP server on port 3000 when start_app.sh does not exist, providing clear guidance to users.

#### Scenario: No start_app.sh - placeholder with guidance
- **WHEN** /home/user/workspace/start_app.sh does not exist
- **THEN** system starts placeholder HTTP server on port 3000
- **AND** placeholder returns JSON response:
  ```json
  {
    "status": "placeholder",
    "message": "no_start_script",
    "detail": "Please create start_app.sh in workspace directory",
    "hint": "Example: npm run dev -- --port 3000 --host 0.0.0.0"
  }
  ```
- **AND** HTTP response code is 503 Service Unavailable

#### Scenario: Placeholder handles CORS preflight
- **WHEN** OPTIONS request is sent to placeholder server
- **THEN** server returns 204 with CORS headers
- **AND** Access-Control-Allow-Origin is set to "*"
- **AND** Access-Control-Allow-Methods includes GET, POST, OPTIONS

### Requirement: Process logs are accessible for debugging

The system SHALL write preview server logs to a predictable location for debugging purposes.

#### Scenario: Log files created
- **WHEN** workspace container is running
- **THEN** log files exist at /home/user/logs/
- **AND** supervisord log at /home/user/logs/supervisord.log
- **AND** preview-server stdout at /home/user/logs/preview-server.log
- **AND** preview-server stderr at /home/user/logs/preview-server-error.log

#### Scenario: Log files are readable
- **WHEN** user or agent reads log files
- **THEN** files are readable by the user account (uid 1000)
- **AND** files contain timestamp and process output

### Requirement: Supervisord manages multiple processes

The system SHALL use supervisord to manage both workspace-client and preview-server processes with proper lifecycle management.

#### Scenario: Both processes running
- **WHEN** workspace container is healthy
- **THEN** supervisord is running as PID 1
- **AND** workspace-client process is running
- **AND** preview-server process is running
- **AND** both processes are children of supervisord

#### Scenario: Container graceful shutdown
- **WHEN** container receives SIGTERM signal
- **THEN** supervisord sends SIGTERM to child processes
- **AND** processes have 10 seconds to shut down gracefully
- **AND** processes are killed with SIGKILL if not stopped in time