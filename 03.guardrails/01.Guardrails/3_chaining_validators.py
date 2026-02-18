from guardrails import Guard
from rich import print
from guardrails.validators import (
    CompetitorCheck,
    ToxicLanguage
)

# Define a list of competitors
competitors = ["ApexMobile", "SamFusionMobile"]

# Initialize Guard and use the CompetitorCheck and ToxicLanguage validators
guard = Guard().use_many(
    CompetitorCheck(
        competitors=competitors, 
        on_fail="fix"  
    ),
    ToxicLanguage(
        validation_method="full",
        threshold=0.5,  
        on_fail="fix"
    )
)

# Validate an output
try: 
    validated_response = guard.validate("My favorite phone is Sony Wave. It's pathetic how inferior the other phones can be at times.")
    print(validated_response)
except Exception as e:
    print(e)
