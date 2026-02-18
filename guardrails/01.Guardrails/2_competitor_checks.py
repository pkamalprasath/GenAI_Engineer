# Import Guard and Validator
from pydantic import BaseModel, Field
from guardrails.validators import CompetitorCheck
from guardrails import Guard
from rich import print

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()  # loads .env into environment variables

os.environ["OPENAI_API_KEY"]= os.getenv('OPENAI_API_KEY')
os.environ["GUARDRAILS_API_KEY"]= os.getenv('GUARDRAILS_API_KEY') 

# Initialize Validator
val = CompetitorCheck(competitors=["Burger Haven", "Sub Wraps"], on_fail="fix") # on_fail="fix/exception"


# Create Pydantic BaseModel
class Product(BaseModel):
    product_name: str
    product_description: str = Field(
        description="Description about the product", validators=[val]
    )


# Create a Guard to check for valid Pydantic output
guard = Guard.from_pydantic(output_class=Product)

product_details = """
        {
            "product_name": "Veggie Delight Sandwich",
            "product_description": "A delicious sandwich filled with fresh veggies, a healthier alternative to fast food; inspired by the flavors of Sub Wraps."
        }
        """
# Run LLM output generating JSON through guard
try:
    output = guard.validate(llm_output=product_details)
    print(guard.history.last.tree) 
except Exception as e:
    print(e)
