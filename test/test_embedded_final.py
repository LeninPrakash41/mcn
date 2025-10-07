from mcn.core_engine.mcn_interpreter import MCNInterpreter


class MCNEmbedded:
    def __init__(self):
        self.interpreter = MCNInterpreter()

    def register_function(self, name: str, func):
        self.interpreter.register_function(name, func)

    def execute(self, script: str, context: dict = None):
        if context:
            self.interpreter.variables.update(context)
        return self.interpreter.execute(script, quiet=True)


def my_existing_function(name, age):
    return f"Hello {name}, you are {age} years old!"


# Test the embedded integration
mcn = MCNEmbedded()
mcn.register_function("my_function", my_existing_function)

script = """
var result = my_function("Alice", 25)
echo result
result
"""

result = mcn.execute(script)
print(f"✅ MCN Embedded works! Result: {result}")
