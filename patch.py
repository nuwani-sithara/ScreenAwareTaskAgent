import re

def patch_app_jsx():
    with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Imports
    content = content.replace(
        "CheckCircle, XCircle, Circle, AlertCircle, Loader, ChevronDown, ChevronUp\n} from 'lucide-react';",
        "CheckCircle, XCircle, Circle, AlertCircle, Loader, ChevronDown, ChevronUp, X\n} from 'lucide-react';"
    )

    # 2. State & effects
    state_setup_old = """export default function App() {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInput]     = useState('');
  const [thinking,  setThinking]  = useState(false);
  const [activeRun, setActiveRun] = useState(null);  // live run state

  const chatAreaRef  = useRef(null);"""

    state_setup_new = """export default function App() {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInput]     = useState('');
  const [thinking,  setThinking]  = useState(false);
  const [activeRun, setActiveRun] = useState(null);  // live run state
  const [toasts, setToasts] = useState([]);

  const chatAreaRef  = useRef(null);
  const addToastRef = useRef();
  const showSystemNotificationRef = useRef();

  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
        Notification.requestPermission();
      }
    }
  }, []);

  useEffect(() => {
    addToastRef.current = (type, message) => {
      const id = Date.now() + Math.random();
      setToasts(prev => [...prev, { id, type, message }]);
      if (type !== 'error' && type !== 'input_needed') {
        setTimeout(() => {
          setToasts(prev => prev.filter(t => t.id !== id));
        }, 8000);
      }
    };
    showSystemNotificationRef.current = (title, options = {}) => {
      if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { ...options });
      }
    };
  }, []);

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };"""
    content = content.replace(state_setup_old, state_setup_new)

    # 3. needs_input
    needs_input_old = """      case 'needs_input':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'waiting_input' } : s
          ),
          inputRequest: {
            stepIndex: event.step_index,
            question:  event.question,
            field:     event.field,
          },
          logs: [...(prev?.logs ?? []), `❓ Input needed: ${event.question}`],
        }));
        break;"""
    needs_input_new = """      case 'needs_input':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'waiting_input' } : s
          ),
          inputRequest: {
            stepIndex: event.step_index,
            question:  event.question,
            field:     event.field,
          },
          logs: [...(prev?.logs ?? []), `❓ Input needed: ${event.question}`],
        }));
        if (addToastRef.current) addToastRef.current('input_needed', event.question);
        if (showSystemNotificationRef.current) showSystemNotificationRef.current('ScreenPilot needs your input', { body: event.question });
        break;"""
    content = content.replace(needs_input_old, needs_input_new)

    # 4. final_report
    final_report_old = """      case 'final_report':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo ?? prev?.todoSteps,
          finalReport: event,
          inputRequest: null,
          logs: [...(prev?.logs ?? []), '📊 Final report ready'],
        }));
        break;"""
    final_report_new = """      case 'final_report':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo ?? prev?.todoSteps,
          finalReport: event,
          inputRequest: null,
          logs: [...(prev?.logs ?? []), '📊 Final report ready'],
        }));
        setMessages(prev => [
          ...prev,
          {
            role: 'agent',
            text: event.report ?? 'Task complete.',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
        ]);
        if (showSystemNotificationRef.current) showSystemNotificationRef.current('Task Complete', { body: event.summary || 'Task finished.' });
        break;"""
    content = content.replace(final_report_old, final_report_new)

    # 5. error
    error_old = """      case 'fatal_error':
      case 'error':
        setActiveRun(prev => ({
          ...prev,
          done: true,
          error: event.message,
          logs: [...(prev?.logs ?? []), `❌ Error: ${event.message}`],
        }));
        setThinking(false);
        break;"""
    error_new = """      case 'fatal_error':
      case 'error':
        setActiveRun(prev => ({
          ...prev,
          done: true,
          error: event.message,
          logs: [...(prev?.logs ?? []), `❌ Error: ${event.message}`],
        }));
        setThinking(false);
        if (addToastRef.current) addToastRef.current('error', event.message);
        if (showSystemNotificationRef.current) showSystemNotificationRef.current('Task Error', { body: event.message });
        break;"""
    content = content.replace(error_old, error_new)

    # 6. Header
    header_old = """      <header className={styles.header}>
        <div className={styles.iconWrapper}>
          <Cpu className={styles.icon} size={28} />
          <div className={styles.pulseRing} />
        </div>"""
    header_new = """      <header className={styles.header}>
        <div className={styles.iconWrapper}>
          <Cpu className={styles.icon} size={28} />
          {activeRun?.inputRequest ? (
            <div className={styles.notificationBadge} title="Input Needed" />
          ) : (
            <div className={styles.pulseRing} />
          )}
        </div>"""
    content = content.replace(header_old, header_new)

    # 7. Clarification panel
    error_panel_old = """            {/* Fatal / connection error */}
            {activeRun.error && (
              <div className={styles.errorPanel}>
                ❌ {activeRun.error}
              </div>
            )}
          </div>"""
    error_panel_new = """            {/* Fatal / connection error */}
            {activeRun.error && activeRun.todoSteps?.length > 0 && (
              <div className={styles.errorPanel}>
                ❌ {activeRun.error}
              </div>
            )}
            
            {/* Clarification panel */}
            {activeRun.error && (!activeRun.todoSteps || activeRun.todoSteps.length === 0) && (
              <div className={styles.clarificationPanel}>
                <div className={styles.clarificationHeader}>
                  <AlertCircle size={20} />
                  Needs Clarification
                </div>
                <p className={styles.clarificationText}>
                  I couldn't understand how to plan this task or couldn't find the necessary elements on screen. 
                  Could you please rephrase or clarify what you want me to do?
                </p>
              </div>
            )}
          </div>"""
    content = content.replace(error_panel_old, error_panel_new)

    # 8. Toasts bottom
    bottom_old = """      {/* ─── Input bar ─── */}
      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <MessageSquare className={styles.inputIcon} size={20} />
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder={thinking ? 'Agent is working…' : 'Describe the task to perform…'}
            disabled={thinking}
          />
        </div>
        <button onClick={sendMessage} disabled={thinking || !input.trim()}>
          <Send size={20} color="#0a192f" />
        </button>
      </div>
    </div>
  );
}"""
    bottom_new = """      {/* ─── Input bar ─── */}
      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <MessageSquare className={styles.inputIcon} size={20} />
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder={thinking ? 'Agent is working…' : 'Describe the task to perform…'}
            disabled={thinking}
          />
        </div>
        <button onClick={sendMessage} disabled={thinking || !input.trim()}>
          <Send size={20} color="#0a192f" />
        </button>
      </div>

      {/* ─── Toasts ─── */}
      <div className={styles.toastContainer}>
        {toasts.map(toast => (
          <div key={toast.id} className={`${styles.toast} ${styles[toast.type === 'input_needed' ? 'inputNeeded' : toast.type] || ''}`}>
            {toast.type === 'error' && <XCircle size={20} color="#ff5555" />}
            {(toast.type === 'warning' || toast.type === 'input_needed') && <AlertCircle size={20} color="#ffbe40" />}
            {toast.type === 'info' && <CheckCircle size={20} color="#64ffda" />}
            <div className={styles.toastContent}>{toast.message}</div>
            <button className={styles.toastClose} onClick={() => removeToast(toast.id)}>
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}"""
    content = content.replace(bottom_old, bottom_new)

    with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(content)

def patch_agentic_loop():
    with open('backend/core/agentic_loop_v2.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. _evaluate_step
    eval_old = """async def _evaluate_step(
    new_screen: dict,
    step: dict,
    user_task: str,
    todo_list: List[dict],
) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/llm/evaluate_step",
            json={
                "instruction": user_task,
                "visual_data": new_screen,
                "step": step,
                "todo_list": todo_list,
            },
        )
        resp.raise_for_status()
        return resp.json()"""
    eval_new = """async def _evaluate_step(
    new_screen: dict,
    step: dict,
    user_task: str,
    todo_list: List[dict],
) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        last_eval = None
        for attempt in range(3):
            resp = await client.post(
                f"{LLM_BASE_URL}/llm/evaluate_step",
                json={
                    "instruction": user_task,
                    "visual_data": new_screen,
                    "step": step,
                    "todo_list": todo_list,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            last_eval = data
            
            # If evaluation succeeded without a fatal parsing error, return immediately
            reason = str(data.get("reason", "")).lower()
            if "no valid json found" not in reason and "evaluation error" not in reason:
                return data
                
            # Otherwise, wait briefly and retry the evaluation call
            await asyncio.sleep(2)
            
        return last_eval"""
    content = content.replace(eval_old, eval_new)

    # 2. _execute_hid_commands_v2
    hid_old = """async def _execute_hid_commands_v2(commands: List[dict]) -> dict:
    \"\"\"
    Corrected HID executor that uses the real cursor position as the anchor
    and does not force the pointer to the top-left corner.
    \"\"\"
    async with httpx.AsyncClient(timeout=30.0) as client:
        cursor_x, cursor_y = _get_cursor_position()

        for idx, cmd in enumerate(commands):
            cmd_type = cmd.get("cmd")"""
    hid_new = """async def _execute_hid_commands_v2(commands: List[dict]) -> dict:
    \"\"\"
    Corrected HID executor that uses the real cursor position as the anchor
    and does not force the pointer to the top-left corner.
    \"\"\"
    async with httpx.AsyncClient(timeout=30.0) as client:
        cursor_x, cursor_y = _get_cursor_position()

        # Pre-execution: window focus at the first movement target
        first_move = next((c for c in commands if c.get("cmd") == "mouse_move"), None)
        if first_move:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                user32.WindowFromPoint.argtypes = [POINT]
                user32.WindowFromPoint.restype = wintypes.HWND
                user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
                user32.GetAncestor.restype = wintypes.HWND
                user32.SetForegroundWindow.argtypes = [wintypes.HWND]

                pt = POINT(int(first_move.get("dx", 0)), int(first_move.get("dy", 0)))
                hwnd = user32.WindowFromPoint(pt)
                if hwnd:
                    root_hwnd = user32.GetAncestor(hwnd, 2) # GA_ROOT
                    if root_hwnd:
                        user32.SetForegroundWindow(root_hwnd)
            except Exception as e:
                logger.warning("Focus window failed: %s", e)

        has_clicked = False
        prev_cmd_type = None

        for idx, cmd in enumerate(commands):
            cmd_type = cmd.get("cmd")

            # Auto prepend a click before typing if not already clicked
            if cmd_type == "type_text":
                if not has_clicked:
                    try:
                        await client.post(HID_API_URL, json={"type": "mouse_click", "payload": {"button": "left"}})
                        await asyncio.sleep(0.25)
                    except Exception:
                        pass
                else:
                    await asyncio.sleep(0.25)

            # Settle delay before clicking if we just moved
            if cmd_type in ("mouse_click", "mouse_double_click"):
                has_clicked = True
                if prev_cmd_type == "mouse_move":
                    await asyncio.sleep(0.15)"""
    content = content.replace(hid_old, hid_new)

    # 3. mouse_move continue
    mouse_move_old = """                    cursor_x += int(p["payload"].get("dx", 0))
                    cursor_y += int(p["payload"].get("dy", 0))
                    await asyncio.sleep(0.04)
                continue"""
    mouse_move_new = """                    cursor_x += int(p["payload"].get("dx", 0))
                    cursor_y += int(p["payload"].get("dy", 0))
                    await asyncio.sleep(0.04)
                prev_cmd_type = cmd_type
                continue"""
    content = content.replace(mouse_move_old, mouse_move_new)

    # 4. other cmds sleep
    other_cmd_old = """            except Exception as exc:
                logger.error("HID command %d failed: %s", idx + 1, exc)
                return {"status": "failed", "error": str(exc), "failed_at": idx}
            await asyncio.sleep(0.2)"""
    other_cmd_new = """            except Exception as exc:
                logger.error("HID command %d failed: %s", idx + 1, exc)
                return {"status": "failed", "error": str(exc), "failed_at": idx}
            prev_cmd_type = cmd_type
            await asyncio.sleep(0.2)"""
    content = content.replace(other_cmd_old, other_cmd_new)

    with open('backend/core/agentic_loop_v2.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_app_jsx()
    patch_agentic_loop()
    print("Patch applied successfully.")
