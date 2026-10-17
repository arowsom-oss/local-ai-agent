from agent_core import run_turn


def ask_in_terminal(name, args):
    print(f"Model wants to run {name} with {args}")
    answer = input("Allow? (y/n) ")
    return answer.strip().lower() == "y"   # only an exact y returns True


def main():
    # Windows spawn imports this module in workers; never start an input loop there.
    messages = []
    try:
        while True:
            text = input("You: ")
            if text.strip().lower() == "quit":
                break
            answer, seconds = run_turn(messages, text, ask_in_terminal, model="auto")
            print("Agent:", answer)
            print(f"[{seconds:.2f}s]")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        from process_guard import stop_all
        from browser_tool import close_browser
        from model_router import release_models
        stop_all()
        close_browser()
        release_models()


if __name__ == "__main__":
    main()
