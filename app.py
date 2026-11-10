from flask import Flask, render_template, request
from guardrail import check_transaction

app = Flask(__name__)

# When you go to your web page, this runs
@app.route('/')
def home():
    # Let's pretend the AI just tried to buy a $200 textbook
    decision, message = check_transaction("near_textbook_shop.testnet", 200.0, "Buying textbook")
    
    # Send this info to our HTML page
    return render_template('approve.html', decision=decision, message=message)

if __name__ == '__main__':
    app.run(debug=True, port=5000)