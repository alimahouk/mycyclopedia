# Mycyclopedia

## The AI-Generated Encyclopedia

![Thumbnail](docs/thumbnail.png)

Mycyclopedia is an AI-powered encyclopedia that leverages advanced language models to generate and curate knowledge. This web application provides an interactive platform for exploring and learning about various topics through AI-generated content.

## Features

- 🤖 AI-powered content generation
- 🌐 Web-based interface
- 🔍 Interactive search functionality
- 📱 Responsive design
- 🔄 Real-time updates
- 🎨 Beautiful and intuitive UI

## Tech Stack

- **Backend**: Python/Flask
- **Frontend**: HTML, CSS, JavaScript
- **AI Integration**: OpenAI API
- **Database**: PostgreSQL
- **Web Server**: uWSGI
- **Deployment**: Docker support

## Prerequisites

- Python 3.11
- PostgreSQL
- Docker (optional, for containerized deployment)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/Mycyclopedia.git
    cd Mycyclopedia
    ```

2. Create and activate a virtual environment:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Set up environment variables:
    Create a `.flaskenv` file in the root directory with the following variables:

    ```text
    FLASK_APP=run.py
    FLASK_ENV=development
    DATABASE_URL=postgresql://username:password@localhost:5432/mycyclopedia
    OPENAI_API_KEY=your_openai_api_key
    ```

5. Initialize the database:

    ```bash
    flask db upgrade
    ```

## Running the Application

### Development Mode

```bash
flask run
```

### Production Mode

```bash
uwsgi --ini hosting/uwsgi.ini
```

### Docker Deployment

```bash
docker build -t mycyclopedia .
docker run -p 5000:5000 mycyclopedia
```

## License

This project is licensed under the terms found in the LICENSE file.

## Author

Created by Ali Mahouk in 2023.
