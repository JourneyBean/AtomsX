# Workspace Client for AtomsX

A Python client that runs inside workspace containers and:
- Connects to backend via WebSocket
- Executes tasks using Claude Agent SDK
- Supports multi-session parallel execution
- Handles session resume, interrupt, and user input

## Process Management

The workspace container uses **supervisord** as PID 1 to manage multiple processes:

- **workspace-client**: Handles WebSocket connection and Claude Agent sessions
- **preview-server**: Runs the preview server on port 3000

### supervisorctl

Check process status:
```bash
supervisorctl status
```

Restart a process:
```bash
supervisorctl restart workspace-client
supervisorctl restart preview-server
```

View logs:
```bash
supervisorctl tail workspace-client
supervisorctl tail preview-server
```

### Log Files

Process logs are stored in `/home/user/logs/`:

| Log File | Description |
|----------|-------------|
| `supervisord.log` | Main supervisord log |
| `workspace-client.log` | workspace-client stdout |
| `workspace-client-error.log` | workspace-client stderr |
| `preview-server.log` | Preview server stdout |
| `preview-server-error.log` | Preview server stderr |

## Preview Server

The preview server automatically starts on port 3000 with the following behavior:

1. If `/home/user/workspace/start_app.sh` exists → executes it
2. If start_app.sh fails → shows placeholder with error message
3. If start_app.sh doesn't exist → shows placeholder with guidance

### Creating start_app.sh

Example scripts for common frameworks:

**Vite (React/Vue):**
```bash
#!/bin/bash
npm run dev -- --port 3000 --host 0.0.0.0
```

**Next.js:**
```bash
#!/bin/bash
npm run dev -- -p 3000 -H 0.0.0.0
```

**Python HTTP Server:**
```bash
#!/bin/bash
python3 -m http.server 3000 --bind 0.0.0.0
```

**Flask:**
```bash
#!/bin/bash
flask run --host 0.0.0.0 --port 3000
```

**FastAPI:**
```bash
#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port 3000
```

### Important Notes

- Preview server must listen on `0.0.0.0:3000` (not just localhost)
- After creating or modifying `start_app.sh`, the workspace container needs to be restarted for changes to take effect