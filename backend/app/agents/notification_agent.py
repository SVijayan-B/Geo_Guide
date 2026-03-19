class NotificationAgent:

    def format_message(self, context, decision):
        time_of_day = context.get("time_of_day", "")
        travel_phase = context.get("travel_phase", "")

        decision_text = decision.get("decision", "")
        reason = decision.get("reason", "")
        action = decision.get("action", "")

        # 🌟 Build message
        message = f"""
✈️ Travel Update

You're traveling during the {time_of_day}.

📍 Suggested Place: {decision_text}

💡 Why?
{reason}

👉 What you can do:
{action}
"""

        return message.strip()