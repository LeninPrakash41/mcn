"""
Real-world MSL integration examples for existing Python projects
"""

from msl_embedded import MSLEmbedded
import json
from datetime import datetime

class CRMWithMSL:
    """CRM system with MSL workflow automation"""
    
    def __init__(self):
        self.msl = MSLEmbedded()
        self._register_crm_functions()
        
    def _register_crm_functions(self):
        self.msl.register_function('send_email', self.send_email)
        self.msl.register_function('create_lead', self.create_lead)
        self.msl.register_function('update_deal', self.update_deal)
        self.msl.register_function('notify_team', self.notify_team)
        
    def send_email(self, to: str, subject: str, body: str = ""):
        print(f"📧 Email sent to {to}: {subject}")
        return {"status": "sent", "to": to}
        
    def create_lead(self, name: str, email: str, source: str = "web"):
        lead_id = f"lead_{len(name)}_{datetime.now().strftime('%H%M%S')}"
        print(f"👤 Lead created: {name} ({lead_id})")
        return {"id": lead_id, "name": name, "email": email}
        
    def update_deal(self, deal_id: str, status: str, amount: float = 0):
        print(f"💰 Deal {deal_id} updated: {status} (${amount})")
        return {"id": deal_id, "status": status, "amount": amount}
        
    def notify_team(self, message: str, channel: str = "sales"):
        print(f"📢 Team notification [{channel}]: {message}")
        return {"sent": True, "channel": channel}

class AIAgentWithMSL:
    """AI Agent builder with MSL behavior scripting"""
    
    def __init__(self):
        self.msl = MSLEmbedded()
        self._register_ai_functions()
        
    def _register_ai_functions(self):
        self.msl.register_function('classify_intent', self.classify_intent)
        self.msl.register_function('extract_entities', self.extract_entities)
        self.msl.register_function('generate_response', self.generate_response)
        
    def classify_intent(self, text: str):
        intents = {
            'help': ['help', 'support', 'issue'],
            'booking': ['book', 'reserve', 'schedule'],
            'info': ['what', 'how', 'when', 'where']
        }
        
        text_lower = text.lower()
        for intent, keywords in intents.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent
        return 'unknown'
        
    def extract_entities(self, text: str):
        entities = {}
        if '@' in text:
            entities['email'] = text.split('@')[0] + '@' + text.split('@')[1].split()[0]
        return entities
        
    def generate_response(self, intent: str, entities: dict = None):
        responses = {
            'help': "I'm here to help! What specific issue are you facing?",
            'booking': "I can help you make a booking. What would you like to book?",
            'info': "I can provide information. What would you like to know?",
            'unknown': "I'm not sure I understand. Could you rephrase that?"
        }
        return responses.get(intent, responses['unknown'])

# Demo usage
if __name__ == "__main__":
    print("🚀 MSL Integration Examples\n")
    
    # CRM Example
    print("1. CRM Workflow Example:")
    crm = CRMWithMSL()
    
    lead_workflow = '''
    var name = customer_name
    var email = customer_email
    
    var lead = create_lead(name, email, "website")
    send_email(email, "Welcome to our platform!")
    notify_team("New lead: " + name + " from website", "sales")
    
    log "Lead workflow completed for: " + name
    "Lead processed successfully"
    '''
    
    result = crm.msl.execute(lead_workflow, {
        'customer_name': 'Alice Johnson',
        'customer_email': 'alice@example.com'
    })
    print(f"Result: {result}\n")
    
    # AI Agent Example
    print("2. AI Agent Example:")
    agent = AIAgentWithMSL()
    
    agent_script = '''
    var message = user_message
    var intent = classify_intent(message)
    var entities = extract_entities(message)
    
    log "Intent: " + intent
    
    if intent == "booking"
        var response = generate_response(intent, entities)
        response
    else
        generate_response(intent, entities)
    '''
    
    result = agent.msl.execute(agent_script, {
        'user_message': 'I want to book a table for tonight'
    })
    print(f"Agent Response: {result}")
    
    print("\n✅ Integration examples completed!")