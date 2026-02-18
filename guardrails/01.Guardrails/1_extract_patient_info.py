from pydantic import BaseModel, Field
from typing import List
from guardrails.validators import ValidRange, ValidChoices
import guardrails as gd
import openai
import json 
from rich import print

class Symptom(BaseModel):
    symptom: str = Field(description="Symptom that a patient is experiencing")
    affected_area: str = Field(description="What part of the body the symptom is affecting", validators=[ValidChoices(choices=['head', 'neck', 'chest'], on_fail="reask")])

class Medication(BaseModel):
    medication: str = Field(description="Name of the medication the patient is taking")
    response: str = Field(description="How the patient is responding to the medication")


class PatientInfo(BaseModel):
    gender: str = Field(description="Patient's gender")
    age: int = Field(validators=[ValidRange(min=0, max=100, on_fail="fix")])
    symptoms: List[Symptom] = Field(description="Symptoms that the patient is currently experiencing. Each symptom should be classified into a separate item in the list.")
    current_meds: List[Medication] = Field(description="Medications the patient is currently taking and their response")

doctors_notes = """45 y/o Male with chronic macular rash to face & hair, worse in beard, eyebrows & nares.
Itchy, flaky, slightly scaly. Moderate response to OTC steroid cream"""

prompt = """
Given the following doctor's notes about a patient, please extract a dictionary that contains the patient's information.

${doctors_notes}

${gr.complete_json_suffix_v2}
"""

guard = gd.Guard.from_pydantic(output_class=PatientInfo, prompt=prompt)
    
# Wrap the OpenAI API call with the `guard` object
res = guard(
    openai.chat.completions.create,
    prompt_params={"doctors_notes": doctors_notes},
    max_tokens=1024,
    temperature=0.3,
)

print(guard.history.last.tree)

