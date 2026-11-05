# Use the Car Chatbot

Follow these steps to download the data and ask the chatbot questions.

## Before you start

You need:

- A Windows computer with Python 3 installed.
- An internet connection for downloading the data.
- This project folder on your computer.

No extra Python packages are needed.

## Start the chatbot

1. Open the project folder in File Explorer.
2. Double-click **`run_chatbot.bat`**.
3. A black window opens. It downloads the data in this order:
   - 2025 car sales
   - 2026 car sales
   - EPA fuel-economy ratings for 2025 and 2026
4. Wait until all three downloads say they completed. The chatbot starts only after all downloads succeed. A browser page should open automatically.
5. In the chatbot page, type a question and click **Ask**, or click one of the sample-question buttons.
6. To start over, click **Clear chat**. This clears the conversation, but keeps the downloaded data.
7. When you are finished, close the black chatbot server window. That stops the app.

Keep the black window open while you use the chatbot.

## Questions to try

- “How many Honda Odysseys sold in 2025?”
- “What is the mileage of a Honda Odyssey?”
- “How many Honda Odyssey sold in 2025 and what is its mileage?”
- “Which model sold the most in 2025?”
- “Which car has the best mileage?”
- “Which electric car has the best mileage?”

For an exact answer, include the make and model. Sales answers use calendar years. Fuel-economy answers use EPA model years, so the two years describe different things.

## If something goes wrong

- **A download fails:** Check your internet connection, then close the window and double-click `run_chatbot.bat` again. The chatbot will not start if a download fails.
- **The browser page does not open:** After the three downloads succeed, open <http://127.0.0.1:8001/> in your browser.
- **Port 8001 is already in use:** Open PowerShell in the project folder and run:

  ```powershell
  $env:PORT = "8002"
  .\run_chatbot.bat
  ```

  Then open <http://127.0.0.1:8002/>.
- **Python is not found:** Install Python 3, then try the batch file again.
- **The chatbot says data is unavailable:** Close the chatbot window and run `run_chatbot.bat` again so it can download all three datasets.

## A note about the data

Sales come from GoodCarBadCar. Its model coverage may vary, and it does not label estimates row by row. The 2026 sales figures cover only the months currently available from the source. EPA ratings describe vehicle model years and configurations; they are not sales-weighted averages. Electric ratings use MPGe and hydrogen ratings use miles per kilogram, so those units are kept separate from MPG.
