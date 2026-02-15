import DeviceShadow from './src/index';
import * as fs from 'fs';
import * as path from 'path';

async function delay(ms: number) {
  return new Promise((res) => setTimeout(res, ms));
}

async function run(filePath?: string) {
  const shadow = new DeviceShadow();

  let commandsFile: string;

  if (filePath) {
    commandsFile = path.resolve(process.cwd(), filePath);
  } else {
    const candidates = [
      path.resolve(__dirname, './example_commands.jsonl'),
      path.resolve(process.cwd(), './example_commands.jsonl')
    ];
    const found = candidates.find((p) => fs.existsSync(p));
    commandsFile = found || candidates[1];
  }

  if (!fs.existsSync(commandsFile)) {
    console.error('Commands file not found (checked locations):', commandsFile);
    process.exit(2);
  }

  const raw = fs.readFileSync(commandsFile, 'utf8');
  const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);

  try {
    console.log('[Runner] Connecting to HID device...');
    await shadow.connect();
    console.log('[Runner] Connected');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      let cmd: any;
      try {
        cmd = JSON.parse(line);
      } catch (e) {
        console.warn('[Runner] Skipping invalid JSON line', i + 1, line);
        continue;
      }

      console.log(`[Runner] Executing (${i + 1}/${lines.length}):`, cmd.cmd || JSON.stringify(cmd));

      try {
        await shadow.executeCommand(cmd);
      } catch (e: any) {
        console.error('[Runner] Command failed:', e && e.message ? e.message : e);
        // Continue to next command after a short pause
        await delay(200);
      }

      // Small pause between commands to keep serial responsive
      await delay(120);
    }

    console.log('[Runner] All commands processed — disconnecting');
    await shadow.disconnect();
    process.exit(0);

  } catch (err: any) {
    console.error('[Runner] Error:', err && err.message ? err.message : err);
    try { await shadow.disconnect(); } catch (e) {}
    process.exit(1);
  }
}

// CLI: optional first arg is path to JSONL file
const inputFile = process.argv[2];
run(inputFile);
