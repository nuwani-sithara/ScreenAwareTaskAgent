import { useState, useRef, useEffect, useCallback } from 'react';
import styles from './Chat.module.css';
import {
  Send, Cpu, MessageSquare, CheckCircle, XCircle, Circle, AlertCircle, Loader,
  ChevronDown, ChevronUp, X, Search, Sparkles, Bell,
  MoreHorizontal, Home, ChevronRight, Bot
} from 'lucide-react';

const THREADS_STORAGE_KEY = 'screenpilot.sidebarThreads.v1';

function loadStoredThreads() {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(THREADS_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistThreads(threads) {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(THREADS_STORAGE_KEY, JSON.stringify(threads));
  } catch {
    // Ignore storage failures and keep the UI working.
  }
}

function buildThreadTitle(task) {
  const text = (task ?? '').trim();
  if (!text) return 'Untitled task';
  return text.length > 44 ? `${text.slice(0, 44).trim()}...` : text;
}

function groupLabelFor(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (sameDay) return 'Today';

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  const isYesterday =
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate();

  if (isYesterday) return 'Yesterday';
  return 'Earlier';
}

function SpinnerIcon({ size = 16 }) {
  return (
    <span style={{ display: 'inline-flex', animation: 'spin 1s linear infinite' }}>
      <Loader size={size} />
    </span>
  );
}

function StepIcon({ status }) {
  switch (status) {
    case 'done':
      return <CheckCircle size={15} className={styles.iconDone} />;
    case 'failed':
      return <XCircle size={15} className={styles.iconFailed} />;
    case 'executing':
      return <SpinnerIcon size={15} />;
    case 'waiting_input':
      return <AlertCircle size={15} className={styles.iconInputWaiting} />;
    default:
      return <Circle size={15} className={styles.iconPending} />;
  }
}

function TodoPanel({ steps, notes }) {
  const done = steps.filter(s => s.status === 'done').length;
  const total = steps.length;

  return (
    <div className={styles.todoPanel}>
      <div className={styles.todoPanelHeader}>
        <span>Task plan</span>
        <span className={styles.todoBadge}>{done}/{total} done</span>
      </div>
      {notes && <p className={styles.todoNotes}>{notes}</p>}
      <div className={styles.todoStepList}>
        {steps.map((step, i) => (
          <div
            key={step.id ?? i}
            className={`${styles.todoStep} ${styles['step_' + step.status] ?? ''}`}
          >
            <span className={styles.stepNum}>{i + 1}</span>
            <span className={styles.stepStatusIcon}>
              <StepIcon status={step.status} />
            </span>
            <span
              className={`${styles.stepAction}
                ${step.status === 'done' ? styles.stepDone : ''}
                ${step.status === 'failed' ? styles.stepFailed : ''}
                ${step.status === 'executing' ? styles.stepActive : ''}
              `}
            >
              {step.action}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LogsPanel({ logs }) {
  if (!logs?.length) return null;
  return (
    <div className={styles.logsPanel}>
      {logs.slice(-6).map((line, i) => (
        <div key={i} className={styles.logEntry}>{line}</div>
      ))}
    </div>
  );
}

function InputRequestPanel({ runId, question, field, onProvide }) {
  const [value, setValue] = useState('');
  const [sent, setSent] = useState(false);
  const inputType = field?.toLowerCase().includes('password') ? 'password' : 'text';

  const handleSend = async () => {
    if (!value.trim()) return;
    setSent(true);
    await onProvide(runId, value);
  };

  return (
    <div className={styles.inputRequestPanel}>
      <div className={styles.inputRequestBadge}>Input required</div>
      <p className={styles.inputRequestQuestion}>{question}</p>
      {sent ? (
        <div className={styles.inputSent}>Sent. Agent is continuing.</div>
      ) : (
        <div className={styles.inputRequestRow}>
          <input
            type={inputType}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={`Enter ${field ?? 'value'}...`}
            className={styles.inputRequestField}
            autoFocus
          />
          <button
            className={styles.inputRequestSend}
            onClick={handleSend}
            disabled={!value.trim()}
            type="button"
          >
            <Send size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function FinalReportCard({ report }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div
      className={`${styles.finalReport} ${report.success ? styles.reportSuccess : styles.reportPartial}`}
    >
      <button
        className={styles.reportHeaderBtn}
        onClick={() => setExpanded(e => !e)}
        type="button"
      >
        <span>{report.success ? 'Success' : 'Attention'} {report.summary}</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <>
          <div className={styles.reportBody}>
            {report.report?.split('\n').map((line, i) =>
              line.trim() ? <p key={i} className={styles.reportLine}>{line}</p> : <br key={i} />
            )}
          </div>

          <div className={styles.reportStats}>
            <span>{report.steps_completed} completed</span>
            {report.steps_failed > 0 && <span>{report.steps_failed} failed</span>}
          </div>

          {report.issues?.length > 0 && (
            <div className={styles.reportIssues}>
              {report.issues.map((iss, i) => (
                <div key={i} className={styles.reportIssueItem}>{iss}</div>
              ))}
            </div>
          )}

          {report.recommendations?.length > 0 && (
            <div className={styles.reportRecs}>
              <strong>Recommendations:</strong>
              {report.recommendations.map((r, i) => (
                <div key={i} className={styles.reportRecItem}>{r}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [activeRun, setActiveRun] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [threads, setThreads] = useState(() => loadStoredThreads());
  const [sidebarQuery, setSidebarQuery] = useState('');
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);

  const chatAreaRef = useRef(null);
  const composerInputRef = useRef(null);
  const addToastRef = useRef();
  const showSystemNotificationRef = useRef();
  const currentThreadIdRef = useRef(null);
  const currentTaskRef = useRef('');

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
  };

  const clearCurrentChat = useCallback(() => {
    setMessages([]);
    setActiveRun(null);
    setThinking(false);
    setInput('');
    currentThreadIdRef.current = null;
    currentTaskRef.current = '';
    setNotificationOpen(false);
    setMoreMenuOpen(false);
  }, []);

  const clearLocalHistory = useCallback(() => {
    setThreads([]);
    try {
      window.localStorage.removeItem(THREADS_STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
    setNotificationOpen(false);
    setMoreMenuOpen(false);
  }, []);

  const focusComposer = useCallback(() => {
    composerInputRef.current?.focus();
    setNotificationOpen(false);
    setMoreMenuOpen(false);
  }, []);

  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages, activeRun]);

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (event.target instanceof Element && event.target.closest(`.${styles.topbarMenuWrap}`)) {
        return;
      }
      setNotificationOpen(false);
      setMoreMenuOpen(false);
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  useEffect(() => {
    persistThreads(threads);
  }, [threads]);

  const upsertThread = useCallback((patch) => {
    setThreads(prev => {
      const next = [...prev];
      const index = next.findIndex(thread => thread.id === patch.id);
      const updatedThread = index >= 0 ? { ...next[index], ...patch } : patch;

      if (index >= 0) {
        next[index] = updatedThread;
      } else {
        next.unshift(updatedThread);
      }

      return next
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        .slice(0, 20);
    });
  }, []);

  const handleEvent = useCallback((event) => {
    switch (event.type) {
      case 'run_started':
        setActiveRun(prev => ({ ...prev, runId: event.run_id }));
        if (currentThreadIdRef.current) {
          upsertThread({
            id: currentThreadIdRef.current,
            updatedAt: new Date().toISOString(),
            status: 'running',
          });
        }
        break;

      case 'todo_created':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo.map(s => ({ ...s, status: 'pending' })),
          notes: event.notes,
          logs: [...(prev?.logs ?? []), `Plan created: ${event.todo.length} steps`],
        }));
        if (currentThreadIdRef.current) {
          upsertThread({
            id: currentThreadIdRef.current,
            updatedAt: new Date().toISOString(),
            status: 'running',
            preview: `Plan created with ${event.todo.length} steps`,
          });
        }
        break;

      case 'step_start':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'executing' } : s
          ),
          logs: [...(prev?.logs ?? []), `Step ${event.step_index + 1}: ${event.step?.action}`],
        }));
        break;

      case 'step_executing':
        setActiveRun(prev => ({
          ...prev,
          logs: [
            ...(prev?.logs ?? []),
            `Sending ${event.hid_count} HID command${event.hid_count !== 1 ? 's' : ''}.`,
          ],
        }));
        break;

      case 'alternate_target':
        setActiveRun(prev => ({
          ...prev,
          logs: [
            ...(prev?.logs ?? []),
            `Trying alternate target ${event.candidate_index}/${event.candidate_total}: ${event.label} at (${event.x}, ${event.y})`,
          ],
        }));
        break;

      case 'step_done':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'done' } : s
          ),
          logs: [
            ...(prev?.logs ?? []),
            `Step ${event.step_index + 1} done (${Math.round((event.confidence ?? 0) * 100)}% confidence)`,
          ],
        }));
        break;

      case 'step_error':
        setActiveRun(prev => ({
          ...prev,
          logs: [...(prev?.logs ?? []), `${event.error} (attempt ${event.attempt})`],
        }));
        break;

      case 'step_permanently_failed':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'failed' } : s
          ),
          logs: [...(prev?.logs ?? []), `${event.message}`],
        }));
        break;

      case 'retrying':
        setActiveRun(prev => ({
          ...prev,
          logs: [
            ...(prev?.logs ?? []),
            `Retrying step ${event.step_index + 1} (attempt ${event.attempt}/${event.max})`,
          ],
        }));
        break;

      case 'needs_input':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'waiting_input' } : s
          ),
          inputRequest: {
            stepIndex: event.step_index,
            question: event.question,
            field: event.field,
          },
          logs: [...(prev?.logs ?? []), `Input needed: ${event.question}`],
        }));
        if (addToastRef.current) addToastRef.current('input_needed', event.question);
        if (showSystemNotificationRef.current) {
          showSystemNotificationRef.current('ScreenPilot needs your input', { body: event.question });
        }
        break;

      case 'input_received':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'executing' } : s
          ),
          inputRequest: null,
          logs: [...(prev?.logs ?? []), `${event.field} received. Continuing.`],
        }));
        break;

      case 'log':
        setActiveRun(prev => ({
          ...prev,
          logs: [...(prev?.logs ?? []).slice(-30), event.message],
        }));
        break;

      case 'screen_captured':
        setActiveRun(prev => ({
          ...prev,
          logs: [...(prev?.logs ?? []), `Screen captured (${event.phase})`],
        }));
        break;

      case 'final_report':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo ?? prev?.todoSteps,
          finalReport: event,
          inputRequest: null,
          logs: [...(prev?.logs ?? []), 'Final report ready'],
        }));
        setMessages(prev => [
          ...prev,
          {
            role: 'agent',
            text: event.report ?? 'Task complete.',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
        ]);
        if (showSystemNotificationRef.current) {
          showSystemNotificationRef.current('Task Complete', { body: event.summary || 'Task finished.' });
        }
        if (currentThreadIdRef.current) {
          upsertThread({
            id: currentThreadIdRef.current,
            title: buildThreadTitle(currentTaskRef.current),
            preview: event.summary || 'Task completed',
            status: event.success ? 'success' : 'warning',
            updatedAt: new Date().toISOString(),
          });
        }
        break;

      case 'done':
        setActiveRun(prev => ({ ...prev, done: true }));
        setThinking(false);
        break;

      case 'fatal_error':
      case 'error':
        setActiveRun(prev => ({
          ...prev,
          done: true,
          error: event.message,
          logs: [...(prev?.logs ?? []), `Connection error: ${event.message}`],
        }));
        setThinking(false);
        if (addToastRef.current) addToastRef.current('error', event.message);
        if (showSystemNotificationRef.current) showSystemNotificationRef.current('Task Error', { body: event.message });
        if (currentThreadIdRef.current) {
          upsertThread({
            id: currentThreadIdRef.current,
            preview: event.message,
            status: 'error',
            updatedAt: new Date().toISOString(),
          });
        }
        break;

      default:
        break;
    }
  }, []);

  const handleProvideInput = useCallback(async (runId, value) => {
    try {
      await fetch(`http://127.0.0.1:8000/provide-input/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });
    } catch (err) {
      console.error('provide-input failed:', err);
    }
  }, []);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || thinking) return;

    const task = input.trim();
    const threadId = `thread-${Date.now()}`;
    currentThreadIdRef.current = threadId;
    currentTaskRef.current = task;
    setInput('');

    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        text: task,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);

    setThinking(true);
    setActiveRun({
      runId: null,
      todoSteps: [],
      notes: '',
      logs: ['Connecting to agent...'],
      inputRequest: null,
      finalReport: null,
      done: false,
      error: null,
    });
    upsertThread({
      id: threadId,
      title: buildThreadTitle(task),
      preview: 'Waiting for agent response...',
      status: 'running',
      updatedAt: new Date().toISOString(),
      task,
    });

    try {
      const response = await fetch('http://127.0.0.1:8000/run-cycle-v2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const line = part.trim();
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.slice(6));
              handleEvent(evt);
            } catch (e) {
              console.warn('SSE parse error:', line, e);
            }
          }
        }
      }
    } catch (err) {
      setActiveRun(prev => ({
        ...prev,
        done: true,
        error: err.message,
        logs: [...(prev?.logs ?? []), `Connection error: ${err.message}`],
      }));
      setThinking(false);
    }
  }, [input, thinking, handleEvent]);

  const quickActions = [
    'Open Chrome and search for Python tutorials',
    'Click the login button and enter credentials',
    'Open Notepad and type Hello World',
    'Check what is currently visible on screen',
  ];

  const sidebarItems = [
    { label: 'Home', icon: Home, active: true },
    { label: 'Chats', icon: MessageSquare, active: false },
  ];

  const filteredThreads = threads.filter(thread => {
    const query = sidebarQuery.trim().toLowerCase();
    if (!query) return true;
    return [thread.title, thread.preview, thread.task]
      .filter(Boolean)
      .some(value => value.toLowerCase().includes(query));
  });

  const groupedThreads = filteredThreads.reduce((acc, thread) => {
    const label = groupLabelFor(thread.updatedAt ?? thread.createdAt ?? new Date().toISOString());
    if (!acc[label]) acc[label] = [];
    acc[label].push(thread);
    return acc;
  }, {});

  const threadGroups = ['Today', 'Yesterday', 'Earlier']
    .map(label => ({ label, items: groupedThreads[label] ?? [] }))
    .filter(group => group.items.length > 0);

  const notificationFeed = [
    ...(activeRun?.inputRequest
      ? [{
        id: 'input-request',
        title: 'Input required',
        detail: activeRun.inputRequest.question,
        tone: 'warning',
      }]
      : []),
    ...(activeRun?.logs?.slice(-3).map((line, index) => ({
      id: `log-${index}`,
      title: 'Live run update',
      detail: line,
      tone: 'info',
    })) ?? []),
    ...toasts.slice(-3).map(toast => ({
      id: `toast-${toast.id}`,
      title: toast.type === 'error' ? 'Error' : 'Notification',
      detail: toast.message,
      tone: toast.type,
    })),
  ].slice(0, 6);

  const showWelcome = messages.length === 0 && !activeRun;

  return (
    <div className={styles.container}>
      <aside className={styles.sidebar}>
        <div className={styles.brandBlock}>
          <div className={styles.brandMark}>
            <Cpu size={20} />
          </div>
          <div>
            <div className={styles.brandName}>ScreenPilot</div>
            <div className={styles.brandTag}>AI workspace</div>
          </div>
        </div>

        <div className={styles.sidebarSearch}>
          <Search size={15} />
          <input
            type="text"
            value={sidebarQuery}
            onChange={e => setSidebarQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
          />
          <span className={styles.shortcutHint}>⌘K</span>
        </div>

        <nav className={styles.sidebarNav}>
          {sidebarItems.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                className={`${styles.sidebarNavItem} ${item.active ? styles.sidebarNavItemActive : ''}`}
                type="button"
                onClick={item.label === 'Chats' ? focusComposer : () => chatAreaRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className={styles.sidebarSection}>
          {threadGroups.length > 0 ? threadGroups.map(group => (
            <div key={group.label} className={styles.threadGroup}>
              <div className={styles.sectionTitle}>{group.label}</div>
              <div className={styles.threadList}>
                {group.items.map(thread => (
                  <button
                    key={thread.id}
                    className={styles.threadItem}
                    type="button"
                    onClick={() => setInput(thread.task || thread.title)}
                    title={thread.task || thread.title}
                  >
                    <div className={styles.threadCopy}>
                      <span className={styles.threadTitle}>{thread.title}</span>
                      <span className={styles.threadPreview}>{thread.preview}</span>
                    </div>
                    <ChevronRight size={14} />
                  </button>
                ))}
              </div>
            </div>
          )) : (
            <div className={styles.emptySidebarState}>
              No conversation history yet.
            </div>
          )}
        </div>

        <div className={styles.sidebarProfile}>
          <div className={styles.profileAvatar}>SP</div>
          <div className={styles.profileMeta}>
            <div className={styles.profileName}>ScreenPilot</div>
            {/* <div className={styles.profilePlan}>Free plan</div> */}
          </div>
          <ChevronDown size={16} />
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.topbar}>
          <button className={styles.topbarPill} type="button">
            <Bot size={15} />
            <span>AI Assistant</span>
            <ChevronDown size={14} />
          </button>

          <div className={styles.topbarActions}>
            <div className={styles.topbarMenuWrap}>
              <button
                className={styles.iconButton}
                type="button"
                aria-label="Notifications"
                aria-expanded={notificationOpen}
                onClick={() => {
                  setNotificationOpen(open => !open);
                  setMoreMenuOpen(false);
                }}
              >
                <Bell size={16} />
                {activeRun?.inputRequest ? <span className={styles.notificationBadge} /> : null}
              </button>
              {notificationOpen && (
                <div className={styles.dropdownPanel}>
                  <div className={styles.dropdownHeader}>
                    <span>Notifications</span>
                    <button type="button" className={styles.dropdownTextButton} onClick={() => setToasts([])}>
                      Clear
                    </button>
                  </div>
                  <div className={styles.dropdownList}>
                    {notificationFeed.length > 0 ? notificationFeed.map(item => (
                      <div key={item.id} className={`${styles.dropdownItem} ${styles[`dropdown_${item.tone}`] || ''}`}>
                        <div className={styles.dropdownItemTitle}>{item.title}</div>
                        <div className={styles.dropdownItemDetail}>{item.detail}</div>
                      </div>
                    )) : (
                      <div className={styles.dropdownEmpty}>No active notifications.</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className={styles.topbarMenuWrap}>
              <button
                className={styles.iconButton}
                type="button"
                aria-label="More options"
                aria-expanded={moreMenuOpen}
                onClick={() => {
                  setMoreMenuOpen(open => !open);
                  setNotificationOpen(false);
                }}
              >
                <MoreHorizontal size={16} />
              </button>
              {moreMenuOpen && (
                <div className={styles.dropdownPanel}>
                  <div className={styles.dropdownList}>
                    <button type="button" className={styles.dropdownAction} onClick={clearCurrentChat}>
                      Start new task
                    </button>
                    <button type="button" className={styles.dropdownAction} onClick={focusComposer}>
                      Focus composer
                    </button>
                    <button type="button" className={styles.dropdownAction} onClick={clearLocalHistory}>
                      Clear local history
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <section className={styles.chatShell}>
          <div className={styles.chatArea} ref={chatAreaRef}>
            {showWelcome && (
              <div className={styles.hero}>
                <div className={styles.heroOrb}>
                  <Sparkles size={32} />
                </div>
                <h2>Good Evening, ScreenPilot.</h2>
                <p>
                  Ask me to plan, observe, and execute screen tasks. I will keep the process
                  transparent, ask for input when needed, and report back when the job is done.
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`${styles.bubble} ${msg.role === 'user' ? styles.user : styles.agent}`}
              >
                <div className={styles.messageMeta}>
                  <span className={styles.messageRole}>
                    {msg.role === 'user' ? 'You' : 'ScreenPilot'}
                  </span>
                  {msg.time && <span className={styles.messageTime}>{msg.time}</span>}
                </div>
                <div className={styles.messageContent}>{msg.text}</div>
              </div>
            ))}

            {activeRun && (
              <div className={styles.runPanel}>
                {activeRun.todoSteps?.length > 0 && (
                  <TodoPanel steps={activeRun.todoSteps} notes={activeRun.notes} />
                )}

                {!activeRun.finalReport && <LogsPanel logs={activeRun.logs} />}

                {activeRun.inputRequest && activeRun.runId && (
                  <InputRequestPanel
                    runId={activeRun.runId}
                    stepIndex={activeRun.inputRequest.stepIndex}
                    question={activeRun.inputRequest.question}
                    field={activeRun.inputRequest.field}
                    onProvide={handleProvideInput}
                  />
                )}

                {activeRun.finalReport && (
                  <FinalReportCard report={activeRun.finalReport} />
                )}

                {activeRun.error && activeRun.todoSteps?.length > 0 && (
                  <div className={styles.errorPanel}>
                    {activeRun.error}
                  </div>
                )}

                {activeRun.error && (!activeRun.todoSteps || activeRun.todoSteps.length === 0) && (
                  <div className={styles.clarificationPanel}>
                    <div className={styles.clarificationHeader}>
                      <AlertCircle size={20} />
                      Needs clarification
                    </div>
                    <p className={styles.clarificationText}>
                      I could not understand how to plan this task or could not find the necessary
                      elements on screen. Please rephrase or clarify what you want me to do.
                    </p>
                  </div>
                )}
              </div>
            )}

            {thinking && !activeRun?.todoSteps?.length && (
              <div className={styles.thinkingDots}>
                <span /><span /><span />
                <span className={styles.thinkingText}>Agent is thinking.</span>
              </div>
            )}
          </div>

        </section>

        <footer className={styles.inputArea}>
          <div className={styles.inputComposer}>
            <div className={styles.inputWrapper}>
              <MessageSquare className={styles.inputIcon} size={18} />
              <input
                ref={composerInputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder={thinking ? 'Agent is working...' : 'Message ScreenPilot...'}
                disabled={thinking}
              />
            </div>
            <button
              className={styles.sendButton}
              onClick={sendMessage}
              disabled={thinking || !input.trim()}
              type="button"
            >
              <Send size={18} />
            </button>
          </div>
        </footer>

        <div className={styles.toastContainer}>
          {toasts.map(toast => (
            <div
              key={toast.id}
              className={`${styles.toast} ${styles[toast.type === 'input_needed' ? 'inputNeeded' : toast.type] || ''}`}
            >
              {toast.type === 'error' && <XCircle size={18} color="#ff8a8a" />}
              {(toast.type === 'warning' || toast.type === 'input_needed') && <AlertCircle size={18} color="#f7c86d" />}
              {toast.type === 'info' && <CheckCircle size={18} color="#86e3cc" />}
              <div className={styles.toastContent}>{toast.message}</div>
              <button className={styles.toastClose} onClick={() => removeToast(toast.id)} type="button">
                <X size={15} />
              </button>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
