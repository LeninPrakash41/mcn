"""
MCN Embedded Integration - Easy integration into existing Python projects
"""

from ..core_engine.mcn_interpreter import MCNInterpreter
from typing import Dict, Any, Callable


class MCNEmbedded:
    """Simplified MCN integration for existing Python applications"""

    def __init__(self):
        self.interpreter = MCNInterpreter()

    def register_function(self, name: str, func: Callable):
        """Register Python function for MCN scripts"""
        self.interpreter.register_function(name, func)

    def set_context(self, context: Dict[str, Any]):
        """Set context variables for MCN execution"""
        self.interpreter.variables.update(context)

    def execute(
        self, script: str, context: Dict[str, Any] = None, quiet: bool = False
    ) -> Any:
        """Execute MCN script with optional context"""
        if context:
            self.set_context(context)
        return self.interpreter.execute(script, quiet=quiet)

    def execute_file(
        self, script_path: str, context: Dict[str, Any] = None, quiet: bool = False
    ) -> Any:
        """Execute MCN script from file"""
        with open(script_path, "r") as f:
            script = f.read()
        return self.execute(script, context, quiet)


# Quick integration examples
def quick_crm_integration():
    """Example: CRM workflow automation"""
    mcn = MCNEmbedded()

    # Register CRM functions
    mcn.register_function("send_email", lambda to, subject: f"Email sent to {to}")
    mcn.register_function("create_lead", lambda name, email: f"Lead {name} created")

    # Execute workflow
    workflow = """
    var lead_name = customer_name
    var lead_email = customer_email

    create_lead(lead_name, lead_email)
    send_email(lead_email, "Welcome to our CRM!")

    log "Lead processed: " + lead_name
    """

    result = mcn.execute(
        workflow, {"customer_name": "John Doe", "customer_email": "john@example.com"}
    )

    return result


def quick_ai_agent_integration():
    """Example: AI Agent behavior scripting"""
    mcn = MCNEmbedded()

    # Register AI functions
    mcn.register_function("classify_intent", lambda text: "support_request")
    mcn.register_function("generate_response", lambda intent: f"Response for {intent}")

    # Agent behavior script
    agent_script = """
    var user_message = input_text
    var intent = classify_intent(user_message)

    if intent == "support_request"
        var response = generate_response(intent)
        log "Generated response: " + response
        response
    else
        "I don't understand that request"
    """

    result = mcn.execute(agent_script, {"input_text": "I need help with my account"})

    return result
