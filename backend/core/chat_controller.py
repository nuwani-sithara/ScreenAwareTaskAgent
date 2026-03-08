import logging

from backend.core.session_manager import session_manager
from backend.utils.input_parser import parse_user_input
from backend.utils.response_formatter import format_agent_response
from backend.core.agentic_loop import run_cycle
from plyer import notification
#--- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

logger.info("=== Agentic AI System Started ===")

logging.basicConfig(level=logging.INFO)

def show_popup(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=5  # seconds
        )
    except Exception as e:
        logging.error(f"❌ Failed to show popup: {e}")

def handle_chat(session_id, user_message):

    logger.info("💬 Chat request received")
    logger.info(f"Session ID: {session_id}")
    logger.info(f"User Message: {user_message}")

    # -----------------------------
    # NEW SESSION
    # -----------------------------
    if not session_id:

        logger.info("🆕 Creating new chat session")

        session_id = session_manager.create_session(user_message)

        logger.info(f"📌 New session created: {session_id}")

        logger.info("🚀 Running agent cycle for initial task")

        result = run_cycle(user_message)

        logger.info(f"📊 Agent result status: {result.get('status')}")

        # CHECK IF INPUT IS REQUIRED
        if result.get("status") == "needs_input":

            logger.info("⚠️ Agent requires additional input from user")

            session_manager.set_missing_fields(
                session_id,
                result["missing_fields"]
            )

            logger.info(f"📝 Missing fields: {result['missing_fields']}")

            # 🔔 Show popup notification for missing input
            popup_text = f"Agent requires the following info:\n• " + "\n• ".join(result["missing_fields"])
            show_popup("Input Required", popup_text)

            return {
                "session_id": session_id,
                "status": "needs_input",
                "message": result["message"],
                "missing_fields": result["missing_fields"]
            }

        logger.info("✅ Agent cycle completed successfully")

        return {
            "session_id": session_id,
            **format_agent_response(result)
        }

    # -----------------------------
    # EXISTING SESSION
    # -----------------------------
    logger.info("🔄 Continuing existing session")

    session = session_manager.get(session_id)

    if not session:
        logger.error(f"❌ Invalid session ID: {session_id}")
        return {"error": "Invalid session"}

    logger.info(f"📂 Session data: {session}")

    # PARSE USER INPUT
    parsed_data = parse_user_input(user_message)

    logger.info(f"🧩 Parsed user input: {parsed_data}")

    # UPDATE SESSION DATA
    session_manager.update_data(session_id, parsed_data)

    collected = session["collected_data"]

    logger.info(f"📥 Collected data so far: {collected}")

    original_prompt = session["original_prompt"]

    logger.info(f"📌 Original prompt: {original_prompt}")

    # BUILD FINAL PROMPT
    full_prompt = f"""
    Task:
    {original_prompt}

    User Provided Data:
    {user_message}
    """

    logger.info("🧠 Sending updated prompt to agent cycle")

    result = run_cycle(full_prompt)

    logger.info("📊 Agent cycle completed")
    logger.info(f"Result status: {result.get('status')}")

    formatted = format_agent_response(result)

    logger.info("📤 Returning formatted response to frontend")

    return {
        "session_id": session_id,
        **formatted
    }