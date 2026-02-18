import re
from guardrails.validators import Validator, register_validator, ValidationResult, PassResult, FailResult
from typing import Any, Dict
import guardrails as gd
from rich import print
from pydantic import BaseModel, Field
import openai

# Social Security Numbers (SSNs): \d{3}[-.\s]??\d{2}[-.\s]??\d{4}: Matches SSNs in the format ###-##-####.
# Individual Taxpayer Identification Numbers (ITINs): \d{9}: Matches nine-digit numeric sequences, which can be ITINs.
# Credit Card Numbers: \d{4}[-.\s]??\d{4}[-.\s]??\d{4}[-.\s]??\d{4}: Matches 16-digit credit card numbers in various formats with optional delimiters -, ., or whitespace.
# Phone Numbers: \d{3}[-.\s]??\d{3}[-.\s]??\d{3}: Matches phone numbers in the format ###-###-###. 
#                (\d{3})\s*\d{3}[-.\s]??\d{4}: Matches phone numbers in the format (###) ###-####.

@register_validator(name="my-pii-filter", data_type="string")
class MyPIIFilter(Validator):
   PII_REGEX = r'\b(?:\d{3}[-.\s]??\d{2}[-.\s]??\d{4}|\d{9}|\d{4}[-.\s]??\d{4}[-.\s]??\d{4}|\d{3}[-.\s]??\d{3}[-.\s]??\d{3}|\(\d{3}\)\s*\d{3}[-.\s]??\d{4}|\d{3}[-.\s]??\d{2}[-.\s]??\d{4})\b'

   def validate(self, value: Any, metadata: Dict) -> ValidationResult:
       if re.search(self.PII_REGEX, value):
           return FailResult(error_message="The text contains Personally Identifiable Information (PII).")
       return PassResult()

class TextAnalysis(BaseModel):
   text: str = Field(
       description="Text to analyze for Personally Identifiable Information (PII).",
       validators=[MyPIIFilter(on_fail="exception")]
   )

prompt = """
Analyze the text for Personally Identifiable Information (PII).
${text}
${gr.complete_json_suffix}
"""

guard = gd.Guard.from_pydantic(output_class=TextAnalysis, prompt=prompt)

try: 
   raw_llm_response, validated_response, *rest = guard(
       openai.completions.create,
       prompt_params={
           "text": "John Doe's SSN is XXX-XX-XXXX."
       },
       model="gpt-3.5-turbo-instruct",
       max_tokens=2048,
       temperature=0,
   )
   print(guard.history.last.tree) 
except Exception as e:
   print(e)
