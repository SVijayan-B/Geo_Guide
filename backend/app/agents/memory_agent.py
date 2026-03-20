class MemoryAgent:
    def __init__(self):
        self.memory_store = {}

    def save(self, user_id, message):
        if user_id not in self.memory_store:
            self.memory_store[user_id] = []

        self.memory_store[user_id].append(message)
    
    
    def get(self, user_id):
        return self.memory_store.get(user_id, [])