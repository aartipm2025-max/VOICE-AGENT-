import requests
import time

API_URL = "http://localhost:8000"

def chat():
    print("=====================================================")
    print("  Advisor Appointment Agent — Live Chat Interface")
    print("  Type 'quit' to exit.")
    print("=====================================================\n")

    # 1. Start session
    try:
        res = requests.post(f"{API_URL}/session")
        res.raise_for_status()
        session_id = res.json()["session_id"]
    except Exception as e:
        print(f"❌ Error: Make sure the FastAPI server is running (run_api.py)")
        print(e)
        return

    # Trigger the greeting by sending an empty message
    res = requests.post(f"{API_URL}/message", json={"session_id": session_id, "text": ""})
    for reply in res.json()["responses"]:
        print(f"\n🤖 Agent: {reply}")
        time.sleep(0.5)

    # 2. Chat loop
    while True:
        print("\n-----------------------------------------------------")
        user_input = input("👤 You:  ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            requests.delete(f"{API_URL}/session/{session_id}")
            print("\nSession closed. Goodbye!")
            break
            
        if not user_input:
            continue

        try:
            res = requests.post(f"{API_URL}/message", json={
                "session_id": session_id,
                "text": user_input
            })
            data = res.json()
            
            for reply in data["responses"]:
                print(f"\n🤖 Agent: {reply}")
                time.sleep(0.5)
                
            if data["completed"]:
                print("\n[Conversation Ended by Agent]")
                break
                
        except Exception as e:
            print(f"Error communicating with the agent: {e}")

if __name__ == "__main__":
    chat()
