# The Guardrail Rules

# Keep track of how much the AI is spending
SPENDING_LIMIT = 15.0  # The human said the max is $15
MAX_TRANSACTIONS_PER_MINUTE = 3 # If it pays more than 3 times in a minute, stop!

# We will pretend this is the AI's memory
transaction_history = []

def check_transaction(recipient, amount, reason):
    """
    This function looks at the AI's request and decides if it is safe.
    It returns: "APPROVE", "DENY", or "ASK_HUMAN"
    """
    
    # Rule 1: Too Much?
    if amount > SPENDING_LIMIT:
        return "ASK_HUMAN", f"Amount ${amount} is over the limit of ${SPENDING_LIMIT}!"
        
    # Rule 2: Too Weird? (Checking if the recipient looks like a scammer)
    # For our demo, we will say if the recipient address is short, it's weird.
    if len(recipient) < 10:
        return "ASK_HUMAN", f"Recipient '{recipient}' looks suspicious!"
        
    # Rule 3: Too Many Times? (The Loop)
    transaction_history.append(amount)
    if len(transaction_history) > MAX_TRANSACTIONS_PER_MINUTE:
        return "DENY", "STOP! The AI is stuck in a payment loop!"
        
    # If it passes all rules, let it through!
    return "APPROVE", "Transaction looks normal."

# --- Testing our Brain ---
if __name__ == "__main__":
    print("Testing Rule 1: Normal Buy")
    print(check_transaction("near_textbook_shop.testnet", 15.0, "Buying textbook"))
    
    print("\nTesting Rule 2: Overspending")
    print(check_transaction("near_textbook_shop.testnet", 200.0, "Buying premium textbook"))
    
    print("\nTesting Rule 3: Weird Scammer")
    print(check_transaction("scammer", 10.0, "Verifying account"))