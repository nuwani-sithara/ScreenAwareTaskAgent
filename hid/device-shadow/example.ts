/**
 * Example: Agent-Driven HID Control
 * 
 * This example demonstrates how an external agent (LLM, script, etc.)
 * can control the host computer through the Device Shadow service.
 */

import DeviceShadow from './src/index';

// Simulate an agent performing a task
async function agentExample() {
  const shadow = new DeviceShadow();
  
  console.log('='.repeat(60));
  console.log('HID Agent Automation Platform - Example');
  console.log('='.repeat(60));
  
  try {
    // Step 1: Connect to HID device
    console.log('\n[1/6] Connecting to ESP32-S3 HID device...');
    await shadow.connect();
    console.log('✓ Connected successfully');
    
    // Wait a moment for stability
    await delay(500);

    // --- LOGIN FLOW using known element coordinates ---
    // Coordinates (centers) from vision data
    const USERNAME = { x: 315, y: 200 };
    const PASSWORD = { x: 315, y: 253 };
    const LOGIN_BTN = { x: 315, y: 320 };

    // Send explicit ACK to firmware to complete handshake
    try {
      await shadow.executeCommand({ cmd: 'ack' });
      console.log('✓ Sent handshake ACK');
    } catch (e) {
      console.warn('WARN: ACK failed (continuing):', e && (e as any).message ? (e as any).message : e);
    }

    // DeviceShadow injects a deterministic top-left anchor before each mouse_move automatically.

    // Move to username field and focus
    console.log('\n[2/6] Move to username and type');
    await shadow.executeCommand({ cmd: 'mouse_move', dx: USERNAME.x, dy: USERNAME.y, smooth: true, duration: 100 });
    await delay(120);
    await shadow.executeCommand({ cmd: 'mouse_click', button: 'left' });
    await delay(150);
    await shadow.executeCommand({ cmd: 'type_text', text: 'admin' });
    await delay(200);

    // Move to password field and type (use absolute coordinates — DeviceShadow anchors to top-left automatically)
    console.log('[3/6] Move to password and type');
    await shadow.executeCommand({ cmd: 'mouse_move', dx: PASSWORD.x, dy: PASSWORD.y, smooth: true, duration: 500 });
    await delay(120);
    await shadow.executeCommand({ cmd: 'mouse_click', button: 'left' });
    await delay(200);
    await shadow.executeCommand({ cmd: 'type_text', text: '1234' });
    await delay(200);

    // Click login button (absolute coordinates)
    console.log('[4/6] Click login button');
    await shadow.executeCommand({ cmd: 'mouse_move', dx: LOGIN_BTN.x, dy: LOGIN_BTN.y, smooth: true, duration: 500 });
    await delay(120);
    await shadow.executeCommand({ cmd: 'mouse_click', button: 'left' });
    await delay(400);

    // Show stats and disconnect
    console.log('[5/6] Done — fetching stats');
    try { const stats = shadow.getStats(); console.log('Stats:', stats); } catch (e) {}
    await shadow.disconnect();
    console.log('✓ Disconnected — login flow finished');
    
  } catch (error: any) {
    console.error('\n✗ Error occurred:', error.message);
    
    // Show device state for debugging
    console.log('\nDevice State:', shadow.getState());
    
    // Attempt cleanup
    try {
      await shadow.disconnect();
    } catch (e) {
      // Ignore disconnect errors
    }
    
    process.exit(1);
  }
}

// Utility function
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// More advanced example: Navigate and interact with UI
async function advancedExample() {
  const shadow = new DeviceShadow();
  
  console.log('Advanced Example: UI Navigation');
  
  try {
    await shadow.connect();
    
    // Open application (Win+R, then type notepad)
    console.log('Opening Notepad...');
    
    // Press Win key
    await shadow.executeCommand({ cmd: 'key_press', key: 0xE3 });  // Win key
    await shadow.executeCommand({ cmd: 'key_release', key: 0xE3 });
    await delay(300);
    
    // Type "notepad"
    await shadow.executeCommand({ cmd: 'type_text', text: 'notepad' });
    await delay(200);
    
    // Press Enter
    await shadow.executeCommand({ cmd: 'key_press', key: 0x28 });  // Enter
    await shadow.executeCommand({ cmd: 'key_release', key: 0x28 });
    await delay(1000);
    
    // Type some content
    await shadow.executeCommand({
      cmd: 'type_text',
      text: 'This is an automated message from the HID agent.\n\nThe agent can:\n- Control mouse\n- Type text\n- Press keyboard shortcuts\n- Interact with any application'
    });
    
    console.log('✓ Advanced example completed');
    
    await shadow.disconnect();
    
  } catch (error: any) {
    console.error('Error:', error.message);
    await shadow.disconnect();
  }
}

// Simple test: just move mouse
async function simpleTest() {
  const shadow = new DeviceShadow();
  
  console.log('Simple Test: Mouse Movement');
  
  try {
    await shadow.connect();
    console.log('Connected!');
    
    console.log('Moving mouse in a square pattern...');
    
    // Move right
    await shadow.executeCommand({ cmd: 'mouse_move', dx: 100, dy: 0, smooth: true });
    await delay(500);
    
    // Move down
    await shadow.executeCommand({ cmd: 'mouse_move', dx: 0, dy: 100, smooth: true });
    await delay(500);
    
    // Move left
    await shadow.executeCommand({ cmd: 'mouse_move', dx: -100, dy: 0, smooth: true });
    await delay(500);
    
    // Move up
    await shadow.executeCommand({ cmd: 'mouse_move', dx: 0, dy: -100, smooth: true });
    
    console.log('✓ Test completed');
    
    await shadow.disconnect();
    
  } catch (error: any) {
    console.error('Error:', error.message);
    await shadow.disconnect();
  }
}

// Run the appropriate example based on command line argument
const exampleType = process.argv[2] || 'basic';

switch (exampleType) {
  case 'basic':
    agentExample();
    break;
  case 'advanced':
    advancedExample();
    break;
  case 'simple':
    simpleTest();
    break;
  default:
    console.log('Usage: node example.js [basic|advanced|simple]');
    process.exit(1);
}
