// src/App.jsx
import { useState, useRef, useEffect } from 'react';
import styles from './Chat.module.css';
import { Send, Cpu, Sparkles, Terminal, Zap, MessageSquare } from 'lucide-react';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const chatAreaRef = useRef(null);



  useEffect(() => {
  
  }, [messages, thinking]);

  const sendMessage = () => {
    if (!input.trim() || thinking) return;

    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        text: input,
        time: new Date().toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit'
        })
      }
    ]);

    setInput('');
    runBackendTask();
  };

  // 🔹 Converts backend JSON → human-friendly message
  const runBackendTask = async () => {
  setThinking(true);

  try {
    const response = await fetch("http://127.0.0.1:8000/run-cycle", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        task: input   // 👈 send user input
      })
    });

    const data = await response.json();

    const success = data?.evaluation?.success;
    const action = data?.action_plan?.action;
    const target = data?.action_plan?.target;

    let messageText = "";

    if (success) {
      messageText = `✅ Test completed successfully

🧠 Planned Action:
• ${action?.toUpperCase()}
• Target: ${target}

🖱️ Execution:
• Action executed successfully on the UI

📊 Evaluation:
• No errors detected
• System behaved as expected`;
    } else {
      messageText = `❌ Test failed during execution

🧠 Planned Action:
• ${action || "Unknown"}
• Target: ${target || "Unknown"}

⚠️ Please retry or review UI state.`;
    }

    setMessages(prev => [
      ...prev,
      { role: "agent", text: messageText }
    ]);

  } catch (err) {
    setMessages(prev => [
      ...prev,
      { role: "agent", text: "❌ Unable to connect to backend service." }
    ]);
  }

  setThinking(false);
};


  const quickActions = [
    'Test login flow',
    'Check mobile responsiveness',
    'Validate form submissions',
    'Run performance audit'
  ];

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.iconWrapper}>
          <Cpu className={styles.icon} size={28} />
          <div className={styles.pulseRing} />
        </div>
        <h1>ScreenPilot AI</h1>
        <span className={styles.subtext}>Autonomous Testing Platform</span>
      </header>

      <div className={styles.chatArea} ref={chatAreaRef}>
        {messages.length === 0 && (
          <div className={styles.welcomeMessage}>
            <div className={styles.welcomeIcon}>
              <Terminal size={48} />
            </div>
            <h2>Welcome to ScreenPilot AI</h2>
            <p>Describe what you want to test, and I'll handle the rest.</p>
            <div className={styles.quickActions}>
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  className={styles.quickAction}
                  onClick={() => setInput(action)}
                >
                  <Zap size={14} />
                  {action}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`${styles.bubble} ${msg.role === 'user' ? styles.user : msg.system ? styles.system : styles.agent}`}>
            <div className={styles.messageContent}>
              {msg.text}
            </div>
            {msg.time && <div className={styles.messageTime}>{msg.time}</div>}
          </div>
        ))}

        {isTyping && (
          <div className={styles.typingIndicator}>
            <MessageSquare size={14} />
            <span>Agent is typing</span>
            <div className={styles.waveContainer}>
              <div className={styles.wave} />
              <div className={styles.wave} />
              <div className={styles.wave} />
              <div className={styles.wave} />
              <div className={styles.wave} />
            </div>
          </div>
        )}

        {thinking && (
          <div className={styles.thinkingDots}>
            <span />
            <span />
            <span />
            <span className={styles.thinkingText}>Processing visual data...</span>
          </div>
        )}
      </div>

      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <MessageSquare className={styles.inputIcon} size={20} />
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder="Describe what you want to test..."
            disabled={thinking}
          />
        </div>
        <button onClick={sendMessage} disabled={thinking}>
          <Send size={24} />
        </button>
      </div>
    </div>
  );
}