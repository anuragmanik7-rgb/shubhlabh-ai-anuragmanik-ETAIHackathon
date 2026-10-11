import os

# Tests never read the local .env and never reach a paid API.
os.environ['PROMOPILOT_SKIP_DOTENV'] = '1'
os.environ.pop('OPENAI_API_KEY', None)
os.environ.pop('GEMINI_API_KEY', None)
os.environ['PROMOPILOT_DISABLE_CHRONOS'] = '1'  # tests never download or load the 120M-parameter model
