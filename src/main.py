from ai_engine import ask_ai

def main():
    print("Personal AI (type 'exit' to quit)\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break

        response = ask_ai(user_input)
        print("\nAI:", response, "\n")

if __name__ == "__main__":
    main()
