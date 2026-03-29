## 1. Core Infrastructure

- [x] 1.1 Create NotificationStore in `stores/notification.ts` with state: notifications array, max limit (5)
- [x] 1.2 Implement NotificationStore actions: showError, showSuccess, showWarning, remove, clear
- [x] 1.3 Add Notification type interface in `types/index.ts` with id, type, message, duration, timestamp
- [x] 1.4 Implement auto-dismiss timer logic in show actions (default 3000ms)

## 2. UI Components

- [x] 2.1 Create Toast.vue component with styling for success/warning/error types
- [x] 2.2 Add close button to Toast component for manual dismiss
- [x] 2.3 Create ToastContainer.vue component with fixed top-right positioning
- [x] 2.4 Add stack layout and animation (fade-in/slide-down) to ToastContainer
- [x] 2.5 Integrate ToastContainer in App.vue root component

## 3. API Error Integration

- [x] 3.1 Add error notification to WorkspaceListView.vue createWorkspace catch block
- [x] 3.2 Add error notification to WorkspaceListView.vue deleteWorkspace catch block
- [x] 3.3 Add error notification to WorkspaceDetailView.vue workspace start/stop operations
- [x] 3.4 Add error notification to stores/session.ts startSession catch block
- [x] 3.5 Add error notification to stores/session.ts sendMessage catch block

## 4. Testing & Verification

- [ ] 4.1 Manually test: trigger workspace creation error, verify toast appears
- [ ] 4.2 Manually test: trigger session error, verify toast appears with correct message
- [ ] 4.3 Manually test: multiple notifications stack correctly
- [ ] 4.4 Manually test: auto-dismiss after 3 seconds
- [ ] 4.5 Manually test: manual dismiss via close button
- [ ] 4.6 Verify: max 5 notifications limit works (oldest removed when exceeded)