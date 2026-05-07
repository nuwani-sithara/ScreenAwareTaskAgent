// src/App.jsx  —  ScreenPilot AI V2 Frontend
// Communicates with the backend V2 agentic loop via SSE streaming.

import { useState, useRef, useEffect, useCallback } from 'react';
import styles from './Chat.module.css';
import {
  Send, Cpu, Terminal, Zap, MessageSquare,
  CheckCircle, XCircle, Circle, AlertCircle, Loader, ChevronDown, ChevronUp
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Spinning loader icon */
function SpinnerIcon({ size = 16 }) {
  return (
    <span style={{ display: 'inline-flex', animation: 'spin 1s linear infinite' }}>
      <Loader size={size} />
    </span>
  );
}

/** Step-status indicator */
function StepIcon({ status }) {
  switch (status) {
    case 'done':          return <CheckCircle  size={15} className={styles.iconDone} />;
    case 'failed':        return <XCircle      size={15} className={styles.iconFailed} />;
    case 'executing':     return <SpinnerIcon  size={15} />;
    case 'waiting_input': return <AlertCircle  size={15} className={styles.iconInputWaiting} />;
    default:              return <Circle       size={15} className={styles.iconPending} />;
  }
}

/** Live todo-list panel */
function TodoPanel({ steps, notes }) {
  const done  = steps.filter(s => s.status === 'done').length;
  const total = steps.length;

  return (
    <div className={styles.todoPanel}>
      <div className={styles.todoPanelHeader}>
        <span>📋 Task Plan</span>
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
                ${step.status === 'done'      ? styles.stepDone    : ''}
                ${step.status === 'failed'    ? styles.stepFailed  : ''}
                ${step.status === 'executing' ? styles.stepActive  : ''}
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

/** Log tail panel (last N messages) */
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

function ScreenshotPanel({ currentScreenshot, screenshots }) {
  if (!currentScreenshot && !screenshots?.length) return null;
  const latest = currentScreenshot || screenshots?.[screenshots.length - 1]?.url;

  return (
    <div className={styles.screenshotPanel}>
      <div className={styles.screenshotHeader}>
        <span>Browser State</span>
        <span>{screenshots?.length ?? 0} captures</span>
      </div>
      {latest && (
        <img
          className={styles.currentScreenshot}
          src={`http://127.0.0.1:8000${latest}`}
          alt="Current browser screenshot"
        />
      )}
      {screenshots?.length > 1 && (
        <div className={styles.screenshotTimeline}>
          {screenshots.slice(-8).map((shot, i) => (
            <img
              key={`${shot.url}-${i}`}
              className={`${styles.screenshotThumb} ${shot.url === latest ? styles.screenshotThumbActive : ''}`}
              src={`http://127.0.0.1:8000${shot.url}`}
              alt={shot.phase || 'Browser screenshot'}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Inline form the user fills when the agent needs data */
function InputRequestPanel({ runId, stepIndex, question, field, onProvide }) {
  const [value,  setValue]  = useState('');
  const [sent,   setSent]   = useState(false);
  const inputType = field?.toLowerCase().includes('password') ? 'password' : 'text';

  const handleSend = async () => {
    if (!value.trim()) return;
    setSent(true);
    await onProvide(runId, value);
  };

  return (
    <div className={styles.inputRequestPanel}>
      <div className={styles.inputRequestBadge}>🤖 Input required</div>
      <p className={styles.inputRequestQuestion}>{question}</p>
      {sent ? (
        <div className={styles.inputSent}>✓ Sent — agent is continuing…</div>
      ) : (
        <div className={styles.inputRequestRow}>
          <input
            type={inputType}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={`Enter ${field ?? 'value'}…`}
            className={styles.inputRequestField}
            autoFocus
          />
          <button
            className={styles.inputRequestSend}
            onClick={handleSend}
            disabled={!value.trim()}
          >
            <Send size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

/** Final report card */
function FinalReportCard({ report }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div
      className={`${styles.finalReport} ${report.success ? styles.reportSuccess : styles.reportPartial}`}
    >
      <button
        className={styles.reportHeaderBtn}
        onClick={() => setExpanded(e => !e)}
      >
        <span>{report.success ? '✅' : '⚠️'} {report.summary}</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <>
          <div className={styles.reportBody}>
            {report.report?.split('\n').map((line, i) =>
              line.trim()
                ? <p key={i} className={styles.reportLine}>{line}</p>
                : <br key={i} />
            )}
          </div>

          <div className={styles.reportStats}>
            <span>✅ {report.steps_completed} completed</span>
            {report.steps_failed > 0 && (
              <span>❌ {report.steps_failed} failed</span>
            )}
          </div>

          {report.issues?.length > 0 && (
            <div className={styles.reportIssues}>
              {report.issues.map((iss, i) => (
                <div key={i} className={styles.reportIssueItem}>⚠ {iss}</div>
              ))}
            </div>
          )}

          {report.recommendations?.length > 0 && (
            <div className={styles.reportRecs}>
              <strong>Recommendations:</strong>
              {report.recommendations.map((r, i) => (
                <div key={i} className={styles.reportRecItem}>→ {r}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

export default function App() {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInput]     = useState('');
  const [thinking,  setThinking]  = useState(false);
  const [activeRun, setActiveRun] = useState(null);  // live run state

  const chatAreaRef  = useRef(null);

  // Auto-scroll to bottom on any content change
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages, activeRun]);

  // ── SSE event handler ──────────────────────────────────────────────────────
  const handleEvent = useCallback((event) => {
    switch (event.type) {

      case 'run_started':
        setActiveRun(prev => ({ ...prev, runId: event.run_id }));
        break;

      case 'todo_created':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo.map(s => ({ ...s, status: 'pending' })),
          notes: event.notes,
          logs: [...(prev?.logs ?? []), `📋 Plan created: ${event.todo.length} steps`],
        }));
        break;

      case 'step_start':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'executing' } : s
          ),
          logs: [...(prev?.logs ?? []), `▶ Step ${event.step_index + 1}: ${event.step?.action}`],
        }));
        break;

      case 'step_executing':
        setActiveRun(prev => ({
          ...prev,
          logs: [
            ...(prev?.logs ?? []),
            `⚡ Executing interaction sequence (${event.interaction_count ?? event.action_count ?? event.hid_count} step${(event.interaction_count ?? event.action_count ?? event.hid_count) !== 1 ? 's' : ''})…`,
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
            `✅ Step ${event.step_index + 1} done (${Math.round((event.confidence ?? 0) * 100)}% confidence)`,
          ],
        }));
        break;

      case 'step_error':
        setActiveRun(prev => ({
          ...prev,
          logs: [...(prev?.logs ?? []), `⚠ ${event.error} (attempt ${event.attempt})`],
        }));
        break;

      case 'step_permanently_failed':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'failed' } : s
          ),
          logs: [...(prev?.logs ?? []), `❌ ${event.message}`],
        }));
        break;

      case 'retrying':
        setActiveRun(prev => ({
          ...prev,
          logs: [
            ...(prev?.logs ?? []),
            `🔄 Retrying step ${event.step_index + 1} (attempt ${event.attempt}/${event.max})`,
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
            question:  event.question,
            field:     event.field,
          },
          logs: [...(prev?.logs ?? []), `❓ Input needed: ${event.question}`],
        }));
        break;

      case 'input_received':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: (prev?.todoSteps ?? []).map((s, i) =>
            i === event.step_index ? { ...s, status: 'executing' } : s
          ),
          inputRequest: null,
          logs: [...(prev?.logs ?? []), `✓ ${event.field} received — continuing…`],
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
          currentScreenshot: event.url ?? prev?.currentScreenshot,
          screenshots: event.history ?? prev?.screenshots ?? [],
          logs: [
            ...(prev?.logs ?? []),
            `📸 Screen captured (${event.phase})`,
          ],
        }));
        break;

      case 'final_report':
        setActiveRun(prev => ({
          ...prev,
          todoSteps: event.todo ?? prev?.todoSteps,
          finalReport: event,
          screenshots: event.screenshots ?? prev?.screenshots ?? [],
          inputRequest: null,
          logs: [...(prev?.logs ?? []), '📊 Final report ready'],
        }));
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
          logs: [...(prev?.logs ?? []), `❌ Error: ${event.message}`],
        }));
        setThinking(false);
        break;

      default:
        break;
    }
  }, []);

  // ── Provide user input to a paused run ────────────────────────────────────
  const handleProvideInput = useCallback(async (runId, value) => {
    try {
      await fetch(`http://127.0.0.1:8000/provide-input/${runId}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ value }),
      });
    } catch (err) {
      console.error('provide-input failed:', err);
    }
  }, []);

  // ── Send a task to the V2 loop ─────────────────────────────────────────────
  const sendMessage = useCallback(async () => {
    if (!input.trim() || thinking) return;

    const task = input.trim();
    setInput('');

    // Add user message bubble
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
      runId:        null,
      todoSteps:    [],
      notes:        '',
      logs:         ['⏳ Connecting to agent…'],
      screenshots:  [],
      currentScreenshot: null,
      inputRequest: null,
      finalReport:  null,
      done:         false,
      error:        null,
    });

    try {
      const response = await fetch('http://127.0.0.1:8000/run-cycle-v2', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ task }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on the SSE event delimiter \n\n
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';   // Keep incomplete tail

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
        done:  true,
        error: err.message,
        logs:  [...(prev?.logs ?? []), `❌ Connection error: ${err.message}`],
      }));
      setThinking(false);
    }
  }, [input, thinking, handleEvent]);

  // ── Quick-action seeds ─────────────────────────────────────────────────────
  const quickActions = [
    'Open YouTube and search for autonomous browser agents',
    'Open Google Docs and type generated viva demo notes',
    'Fill out a demo web form',
    'Open YouTube and search for a topic',
  ];

  const showWelcome = messages.length === 0 && !activeRun;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className={styles.container}>
      {/* ─── Header ─── */}
      <header className={styles.header}>
        <div className={styles.iconWrapper}>
          <Cpu className={styles.icon} size={28} />
          <div className={styles.pulseRing} />
        </div>
        <h1>ScreenPilot AI</h1>
        <span className={styles.subtext}>Autonomous Task Agent v2</span>
      </header>

      {/* ─── Chat area ─── */}
      <div className={styles.chatArea} ref={chatAreaRef}>

        {/* Welcome screen */}
        {showWelcome && (
          <div className={styles.welcomeMessage}>
            <div className={styles.welcomeIcon}><Terminal size={48} /></div>
            <h2>Welcome to ScreenPilot AI</h2>
            <p>
              Describe a browser task. I will plan the workflow, automate the browser,
              capture screenshots, evaluate progress, and ask if I need anything from you.
            </p>
            <div className={styles.quickActions}>
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  className={styles.quickAction}
                  onClick={() => setInput(action)}
                >
                  <Zap size={14} /> {action}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Past messages */}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`${styles.bubble} ${msg.role === 'user' ? styles.user : styles.agent}`}
          >
            <div className={styles.messageContent}>{msg.text}</div>
            {msg.time && <div className={styles.messageTime}>{msg.time}</div>}
          </div>
        ))}

        {/* ─── Live run panel ─── */}
        {activeRun && (
          <div className={styles.runPanel}>

            {/* Todo list */}
            {activeRun.todoSteps?.length > 0 && (
              <TodoPanel steps={activeRun.todoSteps} notes={activeRun.notes} />
            )}

            {/* Activity logs (hidden once final report is ready) */}
            {!activeRun.finalReport && (
              <LogsPanel logs={activeRun.logs} />
            )}

            <ScreenshotPanel
              currentScreenshot={activeRun.currentScreenshot}
              screenshots={activeRun.screenshots}
            />

            {/* User-input request */}
            {activeRun.inputRequest && activeRun.runId && (
              <InputRequestPanel
                runId={activeRun.runId}
                stepIndex={activeRun.inputRequest.stepIndex}
                question={activeRun.inputRequest.question}
                field={activeRun.inputRequest.field}
                onProvide={handleProvideInput}
              />
            )}

            {/* Final report */}
            {activeRun.finalReport && (
              <FinalReportCard report={activeRun.finalReport} />
            )}

            {/* Fatal / connection error */}
            {activeRun.error && (
              <div className={styles.errorPanel}>
                ❌ {activeRun.error}
              </div>
            )}
          </div>
        )}

        {/* Initial "thinking" dots before the todo list appears */}
        {thinking && !activeRun?.todoSteps?.length && (
          <div className={styles.thinkingDots}>
            <span /><span /><span />
            <span className={styles.thinkingText}>Agent is thinking…</span>
          </div>
        )}
      </div>

      {/* ─── Input bar ─── */}
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
}
