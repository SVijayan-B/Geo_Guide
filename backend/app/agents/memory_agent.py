class MemoryAgent:
    # Shared in-process store so multiple agent instances (and LangGraph nodes)
    # can see the same user history.
    # Note: this will be replaced by a vector DB implementation in a later step.
    memory_store = {}

    def __init__(self):
        pass

    def save(self, user_id, message):
        if user_id not in self.memory_store:
            self.memory_store[user_id] = []

        self.memory_store[user_id].append(message)
    
    
    def get(self, user_id):
        return self.memory_store.get(user_id, [])