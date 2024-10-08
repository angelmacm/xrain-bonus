# Discord Bot for Bonus XRAIN Currency

## Project Overview

This project is a Discord bot designed to distribute bonus XRAIN currency to users through slash commands. The bot offers two primary commands:

- `/bonus-xrain`: Provides users with an amount of XRAIN every 48 hours.
- `/biweekly-xrain`: Grants users an amount of XRAIN every two weeks, provided they meet certain requirements.

The bot is implemented in Python using the `discord-py-interactions`, `xrpl-py`, `sqlalchemy`, and `logging` modules. The database backend used is MySQL.

## Features

- **Automated XRAIN Distribution**: Users can claim their bonus XRAIN through predefined intervals using slash commands.
- **Concurrency Management**: Ensures that multiple requests are handled efficiently and without interference.
- **Logging**: Comprehensive logging for debugging and tracking bot activities.
- **Database Integration**: Uses MySQL to store user data and manage transactions.

## Technologies Used

- **Python**: Core programming language.
- **discord-py-interactions**: For handling Discord interactions and slash commands.
- **xrpl-py**: For interacting with the XRPL (XRP Ledger) to manage XRAIN transactions.
- **sqlalchemy**: ORM for handling database interactions with MySQL.
- **logging**: For logging and debugging.

## Setup and Installation

### Prerequisites

- Python 3.8+
- MySQL database
- Discord bot token

### Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/angelmacm/xparrot-claims.git
    cd xparrot-claims
    ```

2. **Create a virtual environment and activate it**:
    ```sh
    python -m venv .
    source bin/activate
    ```

3. **Install the required packages**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Configure the database**:
    Create a MySQL database and update the configuration in the `config.ini` file with your database credentials.

5. **Set up your `config.ini` file**:
    ```ini
    [BOT]
    token = Discord Token Here
    verbose = True

    [XRPL]
    testnet_link = wss://s.altnet.rippletest.net:51233/
    mainnet_link = wss://s1.ripple.com/
    test_mode = False
    verbose = True
    seed = XRP Seed that will send the cryptocurrencies

    [COINS]
    # You can change this hex code to use other coins
    XRAIN = 585241494E000000000000000000000000000000

    [DATABASE]
    db_server = your_db_server
    db_name = your_db_name
    db_username = your_db_username
    db_password = your_db_password
    verbose = True

    ```

### Running the Bot

1. **Run the bot**:
    ```sh
    python bot.py
    ```

## Usage

### Commands

- `/bonus-xrain`
    - Description: Gives users an amount of XRAIN every 48 hours.
    - Usage: `/bonus-xrain`

- `/biweekly-xrain`
    - Description: Gives users an amount of XRAIN every 2 weeks if they meet the requirements.
    - Usage: `/biweekly-xrain`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or support, please contact [angelmac_m@yahoo.com](mailto:angelmac_m@yahoo.com).
