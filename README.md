# Telegram Garmin Training Assistant

A Telegram bot that provides AI-powered training insights and analysis using your Garmin Connect data.

## Features

- 🔐 Secure Garmin Connect integration
- 📊 AI-powered training analysis
- 🏃‍♂️ Personalized workout suggestions
- 🔄 Automatic data synchronization
- 📈 Performance tracking and insights

## Commands

- `/login` - Connect your Garmin account (credentials stored securely)
- `/generate` - Get AI-powered training insights
- `/workout` - Get discipline-specific workout suggestions
- `/roadmap` - View upcoming features
- `/help` - Show detailed command overview

## Security

- Credentials are stored securely with encryption
- All communication is encrypted
- Private data is handled with strict security measures

## Setup

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Configure environment:
- Create a `config.py` file with your API keys:
```python
ANTHROPIC_API_KEY = "your_anthropic_api_key"
TELE_BOT_KEY = "your_telegram_bot_token"
```

3. Run the bot:
```bash
python main.py
```

## Project Structure

```
tele_garmin/
├── utils/           # Utility modules
│   ├── auth.py      # Authentication handling
│   ├── data_extractor.py  # Garmin data extraction
│   ├── prompts.py   # AI system prompts
│   └── report_utils.py    # Report generation
├── config.py        # Configuration
├── main.py         # Main bot logic
└── requirements.txt # Dependencies
```

## Development

The project is under active development. Future features include:
- General Training Q&A
- Smart Workout Suggestions
- Adaptive Training Plans
- Recovery-based Intensity Adjustments

## Contributing

Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
