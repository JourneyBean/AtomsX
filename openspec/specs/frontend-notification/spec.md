# Frontend Notification System

## Purpose

Global notification/Toast system for displaying operation results, error messages, and other user feedback in the frontend application. Notifications appear in the top-right corner, support multiple types (success/warning/error), and auto-dismiss after a configurable duration.

## Requirements

### Requirement: Notification Store manages notification queue
The system SHALL provide a Pinia store that manages a queue of active notifications, supporting add, remove, and clear operations.

#### Scenario: Add notification to queue
- **WHEN** `showError`, `showSuccess`, or `showWarning` is called with a message
- **THEN** a new notification is added to the queue with unique ID, type, message, and timestamp

#### Scenario: Remove notification from queue
- **WHEN** `remove(id)` is called with a valid notification ID
- **THEN** the notification with that ID is removed from the queue

#### Scenario: Clear all notifications
- **WHEN** `clear()` is called
- **THEN** all notifications in the queue are removed

### Requirement: Toast component displays individual notification
The system SHALL provide a Toast component that renders a single notification with appropriate styling based on type (success/warning/error).

#### Scenario: Display error notification
- **WHEN** a notification with type 'error' is rendered
- **THEN** the component displays with red/warning styling and the error message

#### Scenario: Display success notification
- **WHEN** a notification with type 'success' is rendered
- **THEN** the component displays with green/positive styling and the success message

#### Scenario: Display warning notification
- **WHEN** a notification with type 'warning' is rendered
- **THEN** the component displays with yellow/caution styling and the warning message

### Requirement: ToastContainer renders notification queue in fixed position
The system SHALL provide a ToastContainer component positioned at the top-right corner of the viewport, rendering all active notifications stacked vertically.

#### Scenario: Notifications appear in top-right corner
- **WHEN** notifications exist in the store queue
- **THEN** all notifications are displayed stacked vertically in the top-right corner of the screen

#### Scenario: New notifications appear on top
- **WHEN** a new notification is added to the queue
- **THEN** the new notification appears at the top of the stack

### Requirement: Notifications auto-dismiss after configurable duration
The system SHALL automatically remove each notification after a configurable duration (default 3000ms).

#### Scenario: Auto-dismiss after default duration
- **WHEN** a notification is shown without specifying duration
- **THEN** the notification automatically disappears after 3000ms

#### Scenario: Auto-dismiss after custom duration
- **WHEN** a notification is shown with a custom duration (e.g., 5000ms)
- **THEN** the notification automatically disappears after the specified duration

#### Scenario: Manual dismiss before auto-dismiss
- **WHEN** user clicks the close button on a notification
- **THEN** the notification is immediately removed regardless of remaining duration

### Requirement: API error calls trigger error notification
The system SHALL display an error notification when API calls fail, showing the error message from the backend response.

#### Scenario: Workspace creation failure shows notification
- **WHEN** user clicks "Create" button and the API returns an error
- **THEN** an error notification appears with the error message from the response

#### Scenario: Session start failure shows notification
- **WHEN** session creation API call fails
- **THEN** an error notification appears indicating session could not be started

#### Scenario: Message send failure shows notification
- **WHEN** sending a message to the session fails
- **THEN** an error notification appears indicating the message could not be sent

### Requirement: Notification queue has maximum limit
The system SHALL limit the maximum number of simultaneous notifications to prevent UI clutter (default 5).

#### Scenario: Queue exceeds maximum limit
- **WHEN** the notification queue exceeds 5 items
- **THEN** the oldest notification is automatically removed to maintain the limit