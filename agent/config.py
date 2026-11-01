import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DATA_BASE_URL = os.environ["DATA_BASE_URL"]
MODEL = os.environ["MODEL"]

client = OpenAI(
    base_url=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
)
