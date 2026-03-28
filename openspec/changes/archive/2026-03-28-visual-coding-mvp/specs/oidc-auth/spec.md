## ADDED Requirements

### Requirement: User can login via OIDC Provider

The system SHALL provide an OIDC login flow that redirects the user to the configured OIDC Provider, handles the callback, and establishes a user session.

#### Scenario: Successful OIDC login
- **WHEN** user clicks "Login" button on the frontend
- **THEN** system redirects to OIDC Provider authorization endpoint with correct parameters (client_id, redirect_uri, scope, state)
- **AND** after user authenticates on Provider, Provider redirects back to platform callback URL with authorization code
- **AND** system exchanges authorization code for access token and ID token
- **AND** system extracts user identity from ID token (sub, email, name)
- **AND** system creates or updates User record in database
- **AND** system establishes session with session cookie or JWT
- **AND** system redirects user to workspace list page

#### Scenario: OIDC login failure - invalid code
- **WHEN** OIDC Provider returns an error or invalid authorization code
- **THEN** system displays error message "Login failed, please try again"
- **AND** system logs the error for audit
- **AND** system redirects user back to login page

#### Scenario: OIDC login failure - Provider unreachable
- **WHEN** OIDC Provider is unreachable during authorization or token exchange
- **THEN** system displays error message "Authentication service unavailable"
- **AND** system logs the error for audit

### Requirement: User can logout

The system SHALL allow logged-in users to logout and terminate their session.

#### Scenario: Successful logout
- **WHEN** user clicks "Logout" button
- **THEN** system terminates the current session
- **AND** system clears session cookie or invalidates JWT
- **AND** system optionally redirects to OIDC Provider logout endpoint
- **AND** system redirects user to login page

### Requirement: User session persists across requests

The system SHALL maintain user session state across HTTP requests until logout or session expiration.

#### Scenario: Session persistence
- **WHEN** user makes subsequent API requests after login
- **THEN** system recognizes the user from session cookie or JWT
- **AND** system does not require re-authentication

#### Scenario: Session expiration
- **WHEN** user session exceeds configured timeout (default 24 hours)
- **THEN** system terminates the session
- **AND** system redirects user to login page on next request

### Requirement: Unauthenticated access is blocked for protected resources

The system SHALL block access to protected resources for unauthenticated users.

#### Scenario: Unauthenticated API access
- **WHEN** unauthenticated user requests a protected API endpoint (e.g., /api/workspaces)
- **THEN** system returns HTTP 401 Unauthorized
- **AND** system does not reveal any protected data

#### Scenario: Unauthenticated Preview access
- **WHEN** unauthenticated user requests a Preview URL (e.g., *.preview.local)
- **THEN** system returns HTTP 401 Unauthorized or redirects to login page
- **AND** system does not serve Preview content

### Requirement: OIDC login events are audited

The system SHALL record audit logs for all OIDC login and logout events.

#### Scenario: Login audit
- **WHEN** user successfully logs in via OIDC
- **THEN** system creates audit record with: timestamp, user_id, oidc_sub, ip_address, event_type="LOGIN"
- **AND** audit record is stored in database

#### Scenario: Logout audit
- **WHEN** user logs out
- **THEN** system creates audit record with: timestamp, user_id, ip_address, event_type="LOGOUT"
- **AND** audit record is stored in database