# HID API Server

Production-grade REST API server for controlling HID devices remotely.

## Features

✅ **HTTP REST API** - Simple JSON-based command interface  
✅ **ACK-based Reliability** - Waits for command execution confirmation  
✅ **Auto-reconnection** - Handles device disconnections gracefully  
✅ **Health Monitoring** - Device status and statistics endpoints  
✅ **CORS Enabled** - Can be called from web applications  

## Installation

```bash
cd api-server
npm install
```

## Running

### Development
```bash
npm run dev
```

### Production
```bash
npm run build
npm start
```

Server runs on `http://localhost:3015` by default. Set `PORT` environment variable to change.

## API Endpoints

### POST /hid/command

Execute a HID command.

**Request:**
```json
{
  "type": "mouse_move",
  "payload": {
    "dx": 100,
    "dy": 50,
    "smooth": true,
    "duration": 300
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "executionTime": "45ms"
}
```

**Response (500 Error):**
```json
{
  "success": false,
  "error": "Execution failed",
  "message": "Device not responding"
}
```

**Response (503 Service Unavailable):**
```json
{
  "success": false,
  "error": "Device offline"
}
```

### GET /hid/status

Get device status and statistics.

**Response:**
```json
{
  "connected": true,
  "firmwareVersion": "2.0.0",
  "portPath": "COM3",
  "lastHeartbeat": 1707778800000,
  "uptime": 123456,
  "stats": {
    "totalCommands": 42,
    "successRate": 98.5,
    "uptime": 123456
  }
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "HID API Server",
  "version": "2.0.0",
  "timestamp": "2026-02-12T10:00:00.000Z"
}
```

## Command Examples

### Mouse Move
```json
{
  "type": "mouse_move",
  "payload": {
    "dx": 200,
    "dy": 100,
    "smooth": true,
    "duration": 500
  }
}
```

### Mouse Click
```json
{
  "type": "mouse_click",
  "payload": {
    "button": "left"
  }
}
```

### Mouse Drag
```json
{
  "type": "mouse_drag",
  "payload": {
    "dx": 300,
    "dy": 150,
    "button": "left",
    "duration": 600
  }
}
```

### Mouse Scroll
```json
{
  "type": "mouse_scroll",
  "payload": {
    "deltaY": 5
  }
}
```

### Key Combination
```json
{
  "type": "key_combo",
  "payload": {
    "modifiers": ["ctrl", "shift"],
    "key": "t"
  }
}
```

### Type Text
```json
{
  "type": "type_text",
  "payload": {
    "text": "Hello from API!"
  }
}
```

## Usage Examples

### cURL
```bash
# Mouse move
curl -X POST http://localhost:3015/hid/command \
  -H "Content-Type: application/json" \
  -d '{"type":"mouse_move","payload":{"dx":100,"dy":50,"smooth":true}}'

# Get status
curl http://localhost:3015/hid/status

# Health check
curl http://localhost:3015/health
```

### Python
```python
import requests

# Mouse move
response = requests.post('http://localhost:3015/hid/command', json={
    'type': 'mouse_move',
    'payload': {
        'dx': 100,
        'dy': 50,
        'smooth': True
    }
})
print(response.json())

# Key combo (Ctrl+C)
response = requests.post('http://localhost:3015/hid/command', json={
    'type': 'key_combo',
    'payload': {
        'modifiers': ['ctrl'],
        'key': 'c'
    }
})
print(response.json())
```

### JavaScript/Node.js
```javascript
const axios = require('axios');

async function moveMouseand() {
  const response = await axios.post('http://localhost:3015/hid/command', {
    type: 'mouse_move',
    payload: {
      dx: 100,
      dy: 50,
      smooth: true
    }
  });
  console.log(response.data);
}

moveMouse();
```

### Browser/Fetch API
```javascript
fetch('http://localhost:3015/hid/command', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    type: 'mouse_click',
    payload: {
      button: 'left'
    }
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

## Error Handling

The API returns appropriate HTTP status codes:

- **200 OK** - Command executed successfully
- **400 Bad Request** - Invalid request format
- **500 Internal Server Error** - Command execution failed
- **503 Service Unavailable** - Device offline/unavailable

## Security Considerations

⚠️ **WARNING: This API provides unrestricted HID control**

- No authentication or authorization
- No rate limiting by default
- Full keyboard and mouse access

**Recommended security measures:**
- Run on localhost only (firewall external access)
- Use reverse proxy with authentication (nginx, Apache)
- Implement API key authentication
- Add rate limiting middleware
- Run in isolated network segment

## Production Deployment

### systemd Service (Linux)

Create `/etc/systemd/system/hid-api.service`:

```ini
[Unit]
Description=HID API Server
After=network.target

[Service]
Type=simple
User=hidapi
WorkingDirectory=/opt/hid-api-server
ExecStart=/usr/bin/node /opt/hid-api-server/dist/server.js
Restart=always
RestartSec=5
Environment=PORT=3015
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl enable hid-api
sudo systemctl start hid-api
sudo systemctl status hid-api
```

### Docker

Create `Dockerfile`:
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist ./dist
EXPOSE 3015
CMD ["node", "dist/server.js"]
```

Build and run:
```bash
docker build -t hid-api-server .
docker run -d -p 3015:3015 --device=/dev/ttyUSB0 hid-api-server
```

## Monitoring

The API logs all operations to stdout. Integrate with your logging infrastructure:

```bash
# View logs (systemd)
journalctl -u hid-api -f

# View logs (Docker)
docker logs -f <container-id>
```

## Troubleshooting

### Device not connecting
- Check USB cable connection
- Verify device permissions (`ls -l /dev/ttyUSB*` or similar)
- Check API server logs
- Use `/hid/status` endpoint to diagnose

### Commands timing out
- Check device firmware is running
- Verify Serial port settings (115200 baud)
- Check for USB interference
- Monitor `/hid/status` for heartbeat

### High latency
- Reduce `smooth` movement durations
- Disable command logging in production
- Check system load and USB bus utilization

## License

Research and educational use only. Use responsibly.
