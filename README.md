# PDFGrabber Advanced

This is an advanced, unofficial fork of [PDFGrabber](https://github.com/FelixFrog/pdfgrabber), a vendor-agnostic script used to download PDFs from various educational services.

> [!IMPORTANT]
> The original project has been discontinued. This fork aims to maintain and improve the codebase.

## Features

-   **Multi-Service Support**: Downloads from bSmart, Mondadori HUB Scuola, Zanichelli, Pearson, and many more.
-   **Modern TUI**: A beautiful, easy-to-use terminal user interface powered by `rich`.
-   **Smart Management**: Manages tokens and credentials securely.
-   **PDF Processing**: Automatically decrypts and processes downloaded books.

## Installation

1.  **Install Python**: Download and install [Python 3.10+](https://www.python.org/downloads/).
    -   **Windows**: Ensure you check "Add Python to PATH" during installation.
    -   **Linux/macOS**: Use your package manager (e.g., `brew install python3`, `apt install python3`).

2.  **Clone the Repository**:
    ```bash
    git clone https://github.com/rmuxnet/pdfgrabber-advanced
    cd pdfgrabber-advanced
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If you encounter issues (especially on Windows), try `python -m pip install -r requirements.txt`.*

    *Note: You may need to install playwright browsers:*
    ```bash
    playwright install
    ```

## Usage

Run the main script:

-   **Windows**: `python main.py` or `py main.py`
-   **Linux/macOS**: `python3 main.py`

### Main Menu

The new TUI provides a structured menu:

-   **(r) Register new profile**: Create a local profile to save your service credentials.
-   **(d) Download from your libraries**: The main feature. Select a service, log in, list books, and download.
-   **(o) Download from a one-shot link**: Download using a direct link for supported services.
-   **(c) Change profile**: Switch between multiple local profiles.
-   **(t) Manage tokens**: View and delete saved authentication tokens.
-   **(v) View all books**: See a list of all downloaded books.
-   **(q) Quit**: Exit the application.

## Troubleshooting

-   **Login Failed**: clear your tokens using the **(t)** menu or check your credentials.
-   **PyMuPDF Errors**: Ensure you have installed the requirements exactly as specified.

## Disclaimer

This script is provided "as is", without any warranty. The author is not responsible for any misuse. You are responsible for the PDFs you generate and must ensure you comply with copyright laws in your country.
