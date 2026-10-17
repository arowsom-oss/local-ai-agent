from agent_core import run_turn


def ask_in_terminal(name, args):
    print(f"Model wants to run {name} with {args}")
    answer = input("Allow? (y/n) ")
    return answer.strip().lower() == "y"   # only an exact y returns True


messages = []

while True:
    text = input("You: ")
    if text.strip().lower() == "quit":
        break
    answer, seconds = run_turn(messages, text, ask_in_terminal, model="auto")
    print("Agent:", answer)
    print(f"[{seconds:.2f}s]")
